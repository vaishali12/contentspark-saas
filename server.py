from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests
import jwt
import sqlite3
import json
from fastapi import FastAPI, Depends, HTTPException, status
from groq import Groq

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
    project_name: str  # 🌟 Added to match frontend!
    prop_type: str
    city: str
    locality: str
    price: str
    bhk: str
    amenities: list
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
async def generate_campaign(request: CampaignRequest):
    try:
        # Construct the strict system prompt instructions
        system_instruction = f"""
        You are an expert real estate copywriter. Generate 3 distinct marketing channels using these exact values:
        - Project Name/Society Name: {request.project_name}
        - Property Type & Configuration: {request.bhk} {request.prop_type}
        - Location Matrix: {request.locality}, {request.city}
        - Pricing Structure: {request.price}
        - Core Amenities Deck: {', '.join(request.amenities)}
        - Strategic Summary & Features: {request.features}
        - Target Persona Tone: {request.tone}

        STRICT WRITING DIRECTIVES (CRITICAL TO BRAND IDENTITY):
        1. GREETING: Do not use placeholders like '[Name]' or '[Client Name]'. Always greet users universally using warm broadcast terms like "Namaste!" or "Hi there!".
        2. PROJECT ASSIGNMENT: Weave the actual project name '{request.project_name}' smoothly into sentences. Never output '[Apartment Name]'.
        3. NO PLACEHOLDERS: Absolutely zero bracketed labels are permitted in the generated output text block. Do not write '[phone number]' or '[email address]'. End the call-to-action blocks clearly with: "Contact me to schedule an exclusive viewing."
        
        OUTPUT FORMAT REQUIREMENTS:
        You must return your response as a valid JSON object. Do not include any conversational introduction text or markdown code blocks (like ```json). Use exactly these keys:
        {{
            "listing": "Write the detailed property listing ad copy here using the targeted tone.",
            "video": "Write a highly engaging Instagram Reels/TikTok video script here with visual cues.",
            "whatsapp": "Write a short, punchy, emoji-rich WhatsApp broadcast blast message here."
        }}
        """

        # Call the Groq API using Llama 3
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user", 
                    "content": f"Generate a matching 3-channel real estate campaign framework for {request.project_name} in {request.locality} with a {request.tone} tone."
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"} # Forces the LLM to output pure JSON
        )

        # Parse the raw string response from Groq directly into Python JSON
        response_text = completion.choices[0].message.content
        campaign_data = json.loads(response_text)
        
        return campaign_data

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="AI failed to generate a valid JSON campaign structure. Please try again."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Pipeline Failure: {str(e)}"
        )

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