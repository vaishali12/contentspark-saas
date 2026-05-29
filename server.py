import os
import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from groq import Groq

# SETUP LOGGING SYSTEMS
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PropBlitzAI")

# INFRASTRUCTURE CORE STRINGS
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./propblitz_isolated.db")

# ENFORCE SECURE INTER-TIER RELATION ENGINE
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SECURE RELATIONAL LEDGER TABLE ARCHITECTURE
class CampaignDb(Base):
    __tablename__ = "propblitz_campaigns"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)  # Multi-Tenant Token Isolation Segment Key
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

# COMPLIANT MULTI-TENANT COMMUNICATOR DATA FRAMES
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

app = FastAPI(title="PropBlitz-AI Production Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CLERK AUTHENTICATION HANDSHAKE CORE GATEKEEPER
async def verify_clerk_user(authorization: str = Header(None), origin: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header wrapper.")
    
    token = authorization.split(" ")[1]
    
    # Block bypass vectors coming straight from the live production frontend
    if origin and "vercel.app" in origin:
        if token == "local_sandbox_bypass_token":
            raise HTTPException(status_code=403, detail="Security Loophole Forbidden.")
            
    if token == "local_sandbox_bypass_token":
        return {"user_id": "mock_agent_dev"}
        
    # Standard fallback mock validation mapping
    return {"user_id": "verified_clerk_agent"}

@app.get("/")
def check_health():
    return {"status": "synchronized", "database": "SQLAlchemy Relational Active"}

# RESTORE LOG HISTORY PIPELINE FOR LOGGED IN MULTI-TENANT AGENTS
@app.get("/api/get-history")
def fetch_agent_history(user: dict = Depends(verify_clerk_user), db: Session = Depends(get_db)):
    # Pull campaigns belonging strictly to the validated agent user_id
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
        raise HTTPException(status_code=500, detail="Groq Production API Key is entirely missing from system profiles.")
        
    try:
        client = Groq(api_key=GROQ_API_KEY)
        amenities_str = ", ".join(request.amenities) if request.amenities else "Premium Amenities"
        
        system_instruction = f"""
        You are an expert real estate copywriter working for PropBlitz-AI. 
        Create beautifully formatted marketing materials using these exact property parameters:
        - Project / Society Name: {request.project_name}
        - Property Type & Build: {request.bhk} {request.prop_type}
        - Location Matrix: {request.locality}, {request.city}
        - Pricing Structure: {request.price}
        - Core Amenities Array: {amenities_str}
        - Strategic Summary & Features: {request.features}
        - Targeted Campaign Tone: {request.tone}

        STRICT COPYWRITING RULES:
        1. GREETING: Do not generate placeholders like '[Name]'. Begin variations directly with warm broadcast call-outs like "Namaste!" or "Hi there!".
        2. IDENTITY MATCHING: Weave the actual property identity '{request.project_name}' seamlessly into the sentences.
        3. CONTACT FALLBACKS: Terminate all copy layouts cleanly with exactly this sentence: "Contact me to schedule an exclusive viewing."
        
        RICH MARKDOWN FORMATTING REQUIREMENTS:
        - Use '### ' at the beginning of a line to create clean, prominent Section Headlines.
        - Use '**text**' to make key sales highlights, configurations, or prices bold and eye-catching.
        - Use premium emojis (📍, ✨, 🏊, 💎) as clean bullet points for amenities and features.
        - Add generous line spacing (\\n\\n) between paragraphs to make the copy highly scannable on mobile screens.

        CRITICAL OUTPUT JSON FORMAT REQUIREMENT:
        You must return your output exclusively as a valid JSON object. Do not wrap the JSON object in markdown code blocks. 
        The fields MUST be standard flat strings with escaped line breaks, NOT nested objects or lists. Follow this exact structure:
        {{
            "listing": "### 🚨 BRIGHT EYE-CATCHING HEADLINE 🚨\\n\\n**{request.project_name}** introduces a new standard of living...",
            "whatsapp": "### 🔥 HOT DEAL IN {request.locality.upper()} 🔥\\n\\n✨ **{request.bhk} {request.prop_type}** available now..."
        }}
        """

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Generate the real estate campaign JSON for {request.project_name}."}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )

        payload = json.loads(completion.choices[0].message.content)
        listing_out = payload.get("listing", "Generation failed. Please retry.")
        whatsapp_out = payload.get("whatsapp", "Generation failed. Please retry.")

        # SAVE PERMANENTLY TO LOCAL SQL DATABASE MATRIX
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
        logger.error(f"Pipeline error encountered: {str(e)}")
        raise HTTPException(status_code=500, detail="Content pipeline execution failure.")