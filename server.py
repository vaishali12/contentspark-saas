import os
import json
import logging
from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PropBlitzAI")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = "sqlite:///./propblitz_final_replica.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CampaignDb(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    project_name = Column(String, nullable=False)
    listing_raw = Column(Text, nullable=False)
    whatsapp_raw = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CampaignRequest(BaseModel):
    project_name: str
    prop_type: str
    city: str
    locality: str
    price: str
    bhk: str
    amenities: List[str]
    features: str
    tone: str

app = FastAPI(title="PropBlitz-AI Stable Replica")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_clerk_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"user_id": "public_guest_agent"}
    
    token = authorization.split(" ")[1]
    if token == "local_sandbox_bypass_token":
        return {"user_id": "public_guest_agent"}
    
    return {"user_id": "verified_logged_in_agent"}

@app.get("/")
def check_health():
    return {"status": "online"}

@app.get("/api/get-history")
def fetch_agent_history(user: dict = Depends(verify_clerk_user), db: Session = Depends(get_db)):
    campaigns = db.query(CampaignDb).filter(CampaignDb.user_id == user["user_id"]).order_by(CampaignDb.created_at.desc()).all()
    return [{
        "id": c.id,
        "project_name": c.project_name,
        "listing": c.listing_raw,
        "whatsapp": c.whatsapp_raw,
        "date": c.created_at.strftime("%Y-%m-%d")
    } for c in campaigns]

@app.post("/api/generate-campaign")
async def execute_blitz_generation(request: CampaignRequest, user: dict = Depends(verify_clerk_user), db: Session = Depends(get_db)):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API Key is missing.")
        
    try:
        client = Groq(api_key=GROQ_API_KEY)
        amenities_str = ", ".join(request.amenities) if request.amenities else "Premium Amenities"
        
        system_instruction = f"You are a real estate copywriter. Output raw JSON object with keys 'listing' and 'whatsapp' for {request.project_name}."
        user_prompt = f"Topic: {request.features}, Amenities: {amenities_str}, Locality: {request.locality}, Tone: {request.tone}"

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )

        payload = json.loads(completion.choices[0].message.content)
        listing_out = payload.get("listing", "Content generation lagging.")
        whatsapp_out = payload.get("whatsapp", "Content generation lagging.")

        camp_id = f"blitz_{int(datetime.utcnow().timestamp())}"
        db_camp = CampaignDb(
            id=camp_id,
            user_id=user["user_id"],
            project_name=request.project_name,
            listing_raw=listing_out,
            whatsapp_raw=whatsapp_out
        )
        db.add(db_camp)
        db.commit()

        return {"listing": listing_out, "whatsapp": whatsapp_out}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))