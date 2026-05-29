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
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import requests

# SETUP LOGGING & CONFIGURATION
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PropBlitzAI")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./propblitz.db")

# DATABASE ARCHITECTURE MATCHING THE ORIGINAL TOOL
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CampaignDb(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True, index=True)
    project_name = Column(String, nullable=False)
    prop_type = Column(String, nullable=False)
    locality = Column(String, nullable=False)
    city = Column(String, nullable=False)
    price = Column(String, nullable=False)
    bhk = Column(String, nullable=False)
    tone = Column(String, nullable=False)
    features = Column(Text, nullable=False)
    listing_raw = Column(Text, nullable=True)
    whatsapp_raw = Column(Text, nullable=True)
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

# Seed basic credit balances matching reference logic
db_init = SessionLocal()
if not db_init.query(UserMetaDb).filter(UserMetaDb.key == "available_credits").first():
    db_init.add(UserMetaDb(key="available_credits", value_int=150))
    db_init.add(UserMetaDb(key="total_used_credits", value_int=0))
    db_init.commit()
db_init.close()

# REAL ESTATE PROPERTY INPUT SCHEMA
class GenerateCampaignRequest(BaseModel):
    project_name: str
    prop_type: str
    city: str
    locality: str
    price: str
    bhk: str
    amenities: List[str]
    features: str
    tone: str

app = FastAPI(title="PropBlitz-AI Premium Engine", version="2.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_router = APIRouter(prefix="/api")

# BILLING UTILITIES MATCHING ORIGINAL SCHEMAS
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

# HISTORIC ARCHIVE RETRIEVAL
@api_router.get("/campaign/{campaign_id}")
def get_historic_campaign(campaign_id: str, db: Session = Depends(get_db)):
    camp = db.query(CampaignDb).filter(CampaignDb.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign historical archive record not found.")
    return {
        "project_name": camp.project_name,
        "prop_type": camp.prop_type,
        "locality": camp.locality,
        "city": camp.city,
        "price": camp.price,
        "bhk": camp.bhk,
        "tone": camp.tone,
        "features": camp.features,
        "listing": camp.listing_raw,
        "whatsapp": camp.whatsapp_raw
    }

@api_router.get("/user/analytics")
def get_dashboard_analytics(db: Session = Depends(get_db)):
    campaigns = db.query(CampaignDb).order_by(CampaignDb.created_at.desc()).all()
    used_credits = db.query(UserMetaDb).filter(UserMetaDb.key == "total_used_credits").first()
    
    recent_activity = []
    for item in campaigns[:5]:
        recent_activity.append({
            "id": item.id,
            "project_name": item.project_name,
            "tone": item.tone,
            "locality": f"{item.locality}, {item.city}",
            "date": item.created_at.strftime("%Y-%m-%d")
        })
        
    return {
        "metrics": {
            "total_campaigns_created": len(campaigns),
            "credits_consumed": used_credits.value_int if used_credits else 0
        },
        "recent_activity": recent_activity
    }

@api_router.post("/generate")
def generate_campaign(request: GenerateCampaignRequest, db: Session = Depends(get_db)):
    av_credits = db.query(UserMetaDb).filter(UserMetaDb.key == "available_credits").first()
    if not av_credits or av_credits.value_int < 10:
        raise HTTPException(status_code=402, detail="API units exhausted.")

    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq Production API Key is missing from environment.")

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        
        amenities_str = ", ".join(request.amenities) if request.amenities else "Premium Features"
        system_prompt = "You are PropBlitz-AI Pro. You generate structural social distribution content maps adhering strictly to JSON configurations."
        
        user_prompt = f"""Generate a premium real estate marketing campaign for {request.project_name}.
Property Context: {request.bhk} {request.prop_type} inside {request.locality}, {request.city}.
Price Metric: {request.price}
Amenities Array: {amenities_str}
Unique Selling Points & Features: {request.features}
Target Voice Tone: {request.tone}

Return flat JSON with this structure:
{{
  "listing": "### Clear Headline Ad\\n\\n**{request.project_name}** introduces a luxury standard. Contact me to schedule a viewing.",
  "whatsapp": "### 🔥 HOT BROADCAST DEAL 🔥\\n\\n📍 New **{request.bhk}** available now in {request.locality}."
}}"""

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
        
        parsed_json = json.loads(res.json()["choices"][0]["message"]["content"])
    except Exception as e:
        logger.error(f"Groq engine error: {e}")
        raise HTTPException(status_code=502, detail="LLM engine compilation error.")

    av_credits.value_int -= 10
    used_credits = db.query(UserMetaDb).filter(UserMetaDb.key == "total_used_credits").first()
    if used_credits:
        used_credits.value_int += 10
    
    campaign_id = f"blitz_{int(datetime.utcnow().timestamp())}"
    db_camp = CampaignDb(
        id=campaign_id,
        project_name=request.project_name,
        prop_type=request.prop_type,
        locality=request.locality,
        city=request.city,
        price=request.price,
        bhk=request.bhk,
        tone=request.tone,
        features=request.features,
        listing_raw=parsed_json.get("listing", ""),
        whatsapp_raw=parsed_json.get("whatsapp", "")
    )
    db.add(db_camp)
    db.commit()

    return parsed_json

@api_router.post("/export/csv")
def export_csv(request: GenerateCampaignRequest, db: Session = Depends(get_db)):
    latest_camp = db.query(CampaignDb).order_by(CampaignDb.created_at.desc()).first()
    if not latest_camp:
        raise HTTPException(status_code=400, detail="Data record mapping error.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Platform Target", "Optimized Content Stream", "Property Context Anchor", "Tone Axis Configuration"])
    writer.writerow(["Listing Ad", latest_camp.listing_raw, latest_camp.project_name, latest_camp.tone])
    writer.writerow(["WhatsApp Blast", latest_camp.whatsapp_raw, latest_camp.project_name, latest_camp.tone])

    output.seek(0)
    response = StreamingResponse(io.StringIO(output.read()), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=propblitz_bulk_export.csv"
    return response

app.include_router(api_router)