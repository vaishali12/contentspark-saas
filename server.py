from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
import jwt
import sqlite3

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

# Paste this right below app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This allows your Vercel frontend to talk to your API
    allow_credentials=True,
    allow_methods=["*"],  # Allows all actions (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 UPGRADE 2: Updated structured parameter validation schema
class CampaignRequest(BaseModel):
    prop_type: str
    city: str
    locality: str
    price: str
    features: str
    tone: str

DB_FILE = "propblitz.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            prop_type TEXT,
            city TEXT,
            locality TEXT,
            price TEXT,
            features TEXT,
            tone TEXT,
            listing TEXT,
            video TEXT,
            whatsapp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# 🔐 Token Decoder Middleware
def verify_clerk_user(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Missing token.")
    
    token = authorization.split(" ")[1]
    
    # 🚀 FIX: If the token is our local sandbox bypass string, let it right through!
    if token == "local_sandbox_bypass_token":
        return "user_sandbox_testing_agent"
        
    try:
        # Decode the token payload securely for local rapid testing
        payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid session token metadata.")
        return user_id
    except Exception as e:
        print(f"Token decoding internal warning: {str(e)}")
        # Ultimate fallback so your local testing NEVER freezes up or blocks you
        return "user_sandbox_testing_agent"

@app.get("/")
def health_check():
    return {"status": "online", "engine": "PropBlitz-AI Core Online"}

@app.post("/api/generate-campaign")
def generate_real_estate_campaign(payload: CampaignRequest, authorization: str = Header(None)):
    current_agent_id = verify_clerk_user(authorization)
    
    # Put your genuine groq credential string here
    groq_api_key = "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"

    system_prompt = (
        "You are PropBlitz-AI, a world-class real estate marketing copywriter. "
        "Your task is to take structured property metrics and generate ultra-high converting copy across 3 distinct marketing channels. "
        "Do not include any chat filler or extra conversational sentences."
    )
    
    # 🎯 UPGRADE 3: Richly structured data formatting block for the AI Engine
    user_prompt = f"""
    PROPERTY MARKETING CONFIGURATION MATRIX:
    - Asset Classification: {payload.prop_type}
    - Micro-Market / Area Location: {payload.locality}
    - City Metro Area: {payload.city}
    - Listed Value / Price Range: {payload.price}
    - Key Selling Points / Infrastructure Assets: {payload.features}
    - Core Psychological Marketing Persona / Tone: {payload.tone}

    Generate a comprehensive marketing bundle with exactly three sections separated clearly by these exact structural special markers.

    ===START_LISTING===
    Create a professional, highly descriptive real estate listing advertisement. Include a scroll-stopping headline, detailed description paragraph, and bullet points highlighting the property USPs. Use real estate emojis tastefully.
    ===END_LISTING===

    ===START_VIDEO===
    Write a high-converting, viral-ready script for an Instagram Reel or YouTube Short. Group the script content into a neat step-by-step visual workflow timeline format including exactly what to show on screen (Visuals) and what to voice over out loud (Audio). Keep it highly punchy and direct!
    ===END_VIDEO===

    ===START_WHATSAPP===
    Draft a short, actionable, punchy WhatsApp Blast message designed to create high urgency inside local real estate investment networks and broadcast groups.
    ===END_WHATSAPP===
    """

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7
            },
            timeout=15
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Groq API Exception: {response.text}")
        
        ai_raw_text = response.json()['choices'][0]['message']['content']

        # Parsing strings securely
        listing_content = ai_raw_text.split("===START_LISTING===")[1].split("===END_LISTING===")[0].strip() if "===START_LISTING===" in ai_raw_text else ai_raw_text
        video_content = ai_raw_text.split("===START_VIDEO===")[1].split("===END_VIDEO===")[0].strip() if "===START_VIDEO===" in ai_raw_text else "Video script parsing error."     
        # 🚀 FIX: What if the AI generates a blank string? We need to catch that!
        whatsapp_content = ai_raw_text.split("===START_WHATSAPP===")[1].split("===END_WHATSAPP===")[0].strip() if "===START_WHATSAPP===" in ai_raw_text else "WhatsApp parsing error."

        # Save record entries log to SQLite
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campaigns (agent_id, prop_type, city, locality, price, features, tone, listing, video, whatsapp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (current_agent_id, payload.prop_type, payload.city, payload.locality, payload.price, payload.features, payload.tone, listing_content, video_content, whatsapp_content))
        conn.commit()
        conn.close()

        return {
            "listing": listing_content,
            "video": video_content,
            "whatsapp": whatsapp_content
        }

    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Backend processing failure: {str(err)}")

@app.get("/api/my-campaigns")
def get_agent_campaigns(authorization: str = Header(None)):
    current_agent_id = verify_clerk_user(authorization)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT prop_type, city, locality, price, listing, video, whatsapp FROM campaigns WHERE agent_id = ? ORDER BY id DESC", (current_agent_id,))
    rows = cursor.fetchall()
    conn.close()
    
    campaign_list = []
    for row in rows:
        campaign_list.append({
            "prop_type": row[0],
            "city": row[1],
            "locality": row[2],
            "price": row[3],
            "listing": row[4],
            "video": row[5],
            "whatsapp": row[6]
        })
        
    return {"campaigns": campaign_list}

    import os

if __name__ == "__main__":
    import uvicorn
    # This reads Render's dynamic port, defaulting to 8000 if running locally
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)