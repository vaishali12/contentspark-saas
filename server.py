import os
import io
import csv
import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import requests

# SETUP LOGGING & CONFIGURATION
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PropBlitzAI")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./propblitz.db")

# DATABASE ARCHITECTURE MATCHING THE REFERENCE APP
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ClientDb(Base):
    __tablename__ = "clients"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    industry = Column(String, nullable=True)

class CampaignDb(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True, index=True)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    topic = Column(Text, nullable=False)
    tone = Column(String, nullable=False)
    target_audience = Column(String, nullable=True)
    linkedin_raw = Column(Text, nullable=True)
    instagram_raw = Column(Text, nullable=True)
    facebook_raw = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserMetaDb(Base):
    __tablename__ = "user_metadata"
    key = Column(String, primary_key=True)
    value_int = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Seed basic states exactly like your working code
db_init = SessionLocal()
if not db_init.query(UserMetaDb).filter(UserMetaDb.key == "available_credits").first():
    db_init.add(UserMetaDb(key="available_credits", value_int=150))
    db_init.add(UserMetaDb(key="total_used_credits", value_int=0))
    db_init.add(ClientDb(id="c1", name="Apex Tech Solutions", industry="B2B SaaS"))
    db_init.add(ClientDb(id="c2", name="Bloom & Co. Botanicals", industry="E-commerce Retail"))
    db_init.commit()
db_init.close()

# COMPLIANT SCHEMAS
class ClientCreate(BaseModel):
    name: str
    industry: Optional[str] = None

class ClientResponse(BaseModel):
    id: str
    name: str
    industry: Optional[str] = None
    class Config: from_attributes = True

class GenerateContentRequest(BaseModel):
    client_id: str
    topic: str
    tone: str
    target_audience: Optional[str] = None

class TrimRequest(BaseModel):
    text: str
    platform: str
    max_chars: int

app = FastAPI(title="PropBlitz-AI Premium Engine", version="2.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_router = APIRouter(prefix="/api")

TONE_PROMPTS = {
    "professional": "Authoritative B2B thought-leadership tone. Use high-value industry verbs.",
    "thought-provoking": "Disruptive, counter-intuitive concepts. Start with an arresting visual hook.",
    "casual": "Friendly, approachable, and community-driven.",
    "storytelling": "Narrative arc tracking a struggle, an optimization shift, and an ultimate business victory."
}

def call_groq_chat(system_prompt: str, user_prompt: str) -> str:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq Production API Key is missing from environment.")
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code != 200:
            raise Exception(f"Groq error: {res.text}")
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq fallback error: {e}")
        raise HTTPException(status_code=502, detail="LLM engine compilation error.")

# CLIENT LIFECYCLE ROUTES
@api_router.get("/clients", response_model=List[ClientResponse])
def list_clients(db: Session = Depends(get_db)):
    return db.query(ClientDb).all()

@api_router.post("/clients", response_model=ClientResponse)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    if not client.name.strip():
        raise HTTPException(status_code=400, detail="Client name cannot be blank.")
    new_id = f"c_{int(datetime.utcnow().timestamp())}"
    db_client = ClientDb(id=new_id, name=client.name.strip(), industry=client.industry.strip() if client.industry else "General")
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

# BILLING UTILITIES
@api_router.get("/user/billing")
def get_billing_status(db: Session = Depends(get_db)):
    av = db.query(UserMetaDb).filter(UserMetaDb.key == "available_credits").first()
    us = db.query(UserMetaDb).filter(UserMetaDb.key == "total_used_credits").first()
    return {"available": av.value_int if av else 0, "total_used": us.value_int if us else 0}

@api_router.post("/user/billing/reset")
def reset_billing_credits(db: Session = Depends(get_db)):
    av = db.query(UserMetaDb).filter(UserMetaDb.key == "available_credits").first()
    if av:
        av.value_int = 150
        db.commit()
    return {"status": "success", "available": 150}

# HISTORIC RETRIEVAL PIPELINE
@api_router.get("/campaign/{campaign_id}")
def get_historic_campaign(campaign_id: str, db: Session = Depends(get_db)):
    camp = db.query(CampaignDb).filter(CampaignDb.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign historical archive record not found.")
    return {
        "topic": camp.topic,
        "tone": camp.tone,
        "target_audience": camp.target_audience,
        "linkedin": json.loads(camp.linkedin_raw or "{}"),
        "instagram": json.loads(camp.instagram_raw or "{}"),
        "facebook": json.loads(camp.facebook_raw or "{}")
    }

@api_router.get("/user/analytics")
def get_dashboard_analytics(client_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CampaignDb)
    if client_id:
        query = query.filter(CampaignDb.client_id == client_id)
    
    campaigns = query.order_by(CampaignDb.created_at.desc()).all()
    used_credits = db.query(UserMetaDb).filter(UserMetaDb.key == "total_used_credits").first()
    
    recent_activity = []
    for item in campaigns[:5]:
        recent_activity.append({
            "id": item.id,
            "topic": item.topic,
            "tone": item.tone.title(),
            "audience": item.target_audience or "General Audience",
            "date": item.created_at.strftime("%Y-%m-%d")
        })
        
    return {
        "metrics": {
            "total_campaigns_created": len(campaigns),
            "active_client_profiles": db.query(ClientDb).count(),
            "credits_consumed": used_credits.value_int if used_credits else 0
        },
        "recent_activity": recent_activity
    }

@api_router.post("/generate")
def generate_campaign(request: GenerateContentRequest, db: Session = Depends(get_db)):
    av_credits = db.query(UserMetaDb).filter(UserMetaDb.key == "available_credits").first()
    if not av_credits or av_credits.value_int < 10:
        raise HTTPException(status_code=402, detail="API units exhausted.")

    client = db.query(ClientDb).filter(ClientDb.id == request.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client context resolution failure.")

    tone_instruction = TONE_PROMPTS.get(request.tone.lower(), TONE_PROMPTS["professional"])
    audience = request.target_audience or f"General audience focused on {client.industry}."

    system_prompt = "You are PropBlitz-AI Premium Engine. You generate structural social distribution content maps adhering strictly to JSON configurations."
    user_prompt = f"""Generate a campaign for {client.name} (Industry: {client.industry}).
Topic: {request.topic}
Tone: {tone_instruction}
ICP Segment: {audience}

Return flat JSON with this structure:
{{
  "linkedin": {{ "content": "LinkedIn post content text with 3-5 tags at the bottom" }},
  "instagram": {{ "caption": "Instagram text caption", "visual_hook": "Visual setup description", "hashtags": ["tag1", "tag2"] }},
  "facebook": {{ "content": "Facebook post content", "engagement_prompt": "Engagement poll question" }}
}}"""

    raw_response = call_groq_chat(system_prompt, user_prompt)
    try:
        parsed_json = json.loads(raw_response)
    except:
        raise HTTPException(status_code=502, detail="LLM returned invalid formatting structure.")

    av_credits.value_int -= 10
    used_credits = db.query(UserMetaDb).filter(UserMetaDb.key == "total_used_credits").first()
    if used_credits:
        used_credits.value_int += 10
    
    campaign_id = f"camp_{int(datetime.utcnow().timestamp())}"
    db_camp = CampaignDb(
        id=campaign_id,
        client_id=request.client_id,
        topic=request.topic,
        tone=request.tone,
        target_audience=request.target_audience,
        linkedin_raw=json.dumps(parsed_json.get("linkedin", {})),
        instagram_raw=json.dumps(parsed_json.get("instagram", {})),
        facebook_raw=json.dumps(parsed_json.get("facebook", {}))
    )
    db.add(db_camp)
    db.commit()

    return parsed_json

@api_router.post("/trim")
def trim_text(request: TrimRequest):
    system_prompt = "You are an expert copywriter. Reduce text lengths down to clean constraints without dropping core hooks or structural tags."
    user_prompt = f"Condense this text down to fit tightly within {request.max_chars} characters while preserving active calls-to-action or hashtags.\nText:\n{request.text}"
    raw_text = call_groq_chat(system_prompt, f"Return a JSON object with a key 'trimmed_text'.\n{user_prompt}")
    try:
        p = json.loads(raw_text)
        return {"trimmed_content": p.get("trimmed_text", request.text[:request.max_chars])}
    except:
        return {"trimmed_content": raw_text[:request.max_chars]}

@api_router.post("/export/csv")
def export_csv(request: GenerateContentRequest, db: Session = Depends(get_db)):
    client = db.query(ClientDb).filter(ClientDb.id == request.client_id).first()
    latest_camp = db.query(CampaignDb).filter(CampaignDb.client_id == request.client_id).order_by(CampaignDb.created_at.desc()).first()
    if not latest_camp or not client:
        raise HTTPException(status_code=400, detail="Data record mapping error.")

    li = json.loads(latest_camp.linkedin_raw or "{}").get("content", "")
    insta_data = json.loads(latest_camp.instagram_raw or "{}")
    fb_data = json.loads(latest_camp.facebook_raw or "{}")

    ins = f"{insta_data.get('caption','')}\n\n[Visual Hook: {insta_data.get('visual_hook','')}]\n" + " ".join([f"#{t}" for t in insta_data.get("hashtags", [])])
    fb = f"{fb_data.get('content','')}\n\n💬 Q: {fb_data.get('engagement_prompt','')}"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Platform Target", "Optimized Content Stream", "Client Context Anchor", "Tone Axis Configuration"])
    writer.writerow(["LinkedIn", li, client.name, latest_camp.tone])
    writer.writerow(["Instagram", ins, client.name, latest_camp.tone])
    writer.writerow(["Facebook", fb, client.name, latest_camp.tone])

    output.seek(0)
    response = StreamingResponse(io.StringIO(output.read()), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=propblitz_bulk_{request.client_id}.csv"
    return response

app.include_router(api_router)