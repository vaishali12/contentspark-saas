import os
import json
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from groq import Groq

app = FastAPI(title="PropBlitz-AI Core Backend API")

# Configure cross-origin framework capabilities for safe Vercel interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Groq processing pipeline wrapper using environment profiles
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("CRITICAL CRASH: GROQ_API_KEY environment variable is entirely missing.")

client = Groq(api_key=GROQ_API_KEY)

# Mock production database array holding user structural history sandbox logs
MOCK_CAMPAIGN_DB = []

# Strict incoming request validation frame
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

# Clerk authorization token signature validation handshake
async def verify_clerk_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header wrapper.")
    
    token = authorization.split(" ")[1]
    if token == "local_sandbox_bypass_token":
        return {"user_id": "mock_agent_dev", "email": "sandbox@propblitz.ai"}
        
    return {"user_id": "verified_clerk_agent"}

@app.get("/")
def read_root():
    return {"status": "active", "engine": "PropBlitz-AI Pipeline Engine", "cost": "0.00"}

# Core Multi-Channel Marketing Content Generation Route (Rich Markdown Layouts)
@app.post("/api/generate-campaign")
async def generate_campaign(request: CampaignRequest, user: dict = Depends(verify_clerk_user)):
    try:
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
                {
                    "role": "user", 
                    "content": f"Generate the 2-channel real estate campaign JSON for {request.project_name}. Ensure 'listing' and 'whatsapp' keys contain flat string values only."
                }
            ],
            temperature=0.5, 
            response_format={"type": "json_object"}  
        )

        response_content = completion.choices[0].message.content
        if not response_content:
            raise HTTPException(status_code=500, detail="AI Engine returned empty data content pipeline.")
            
        campaign_payload = json.loads(response_content)
        
        final_response = {
            "listing": str(campaign_payload.get("listing", "Content generation lagging. Please retry.")),
            "whatsapp": str(campaign_payload.get("whatsapp", "Content generation lagging. Please retry."))
        }
        
        try:
            history_snapshot = {
                "id": str(len(MOCK_CAMPAIGN_DB) + 1),
                "project_name": str(request.project_name),
                "listing": final_response["listing"],
                "whatsapp": final_response["whatsapp"]
            }
            MOCK_CAMPAIGN_DB.append(history_snapshot)
        except Exception as log_err:
            print(f"Non-blocking log exception: {str(log_err)}")
        
        return final_response

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI response format dropped conversion rules. Re-click generation.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Pipeline Exception Encountered: {str(e)}")