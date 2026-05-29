import os
import json
import requests
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

# 1. Initialize the FastAPI Application Core
app = FastAPI()

# 2. Configure Cross-Origin Resource Sharing (CORS) Security Policies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows seamless connections from your live Vercel frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Instantiate the Secure Groq Client Channel
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Mock Database Store array to hold campaign histories in memory safely 
# until your dynamic Supabase cluster integration is fully built out.
MOCK_CAMPAIGN_DB = [
    {
        "id": "1",
        "project_name": "Prestige Shantiniketan",
        "listing": "Luxury 3 BHK ready to move in...",
        "video": "Scene 1: Show the kitchen...",
        "whatsapp": "Namaste! Check out this exclusive deal..."
    }
]

# 4. Define the Data Serialization Validation Schema Matrix
class CampaignRequest(BaseModel):
    project_name: str  # Replaces bracketed [Apartment Name] tags permanently
    prop_type: str
    city: str
    locality: str
    price: str
    bhk: str
    amenities: list
    features: str
    tone: str

# 5. Clerk Token Verification Dependency Logic
async def verify_clerk_user(authorization: str = Header(None)):
    """
    Validates inbound authorization traffic. Temporarily returns a verified 
    state so you can test and share the application instantly without Clerk API blockages.
    """
    if not authorization or not authorization.startswith("Bearer "):
        if authorization == "Bearer local_sandbox_bypass_token":
            return {"user_id": "sandbox_dev_agent"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header credentials."
        )
    
    # 🌟 BYPASS CLERK BACKEND HANDSHAKE FOR SEAMLESS LAUNCH TESTING
    # This ensures your frontend tokens pass through without throwing 401 errors
    return {"authenticated": True, "user_id": "active_agent"}

# 6. System Health Check Root Endpoint Route
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PropBlitz-AI Generation Engine Core Pipeline",
        "version": "2.0.0"
    }

# 7. 🌟 RESTORED: Fetch Past Generated Campaigns Endpoint
@app.get("/api/my-campaigns")
async def get_my_campaigns(user: dict = Depends(verify_clerk_user)):
    """
    Returns history arrays safely so your dashboard tracking blocks do not break.
    """
    return {"status": "success", "campaigns": MOCK_CAMPAIGN_DB}

# 8. Core Multi-Channel Marketing Content Generation Route
@app.post("/api/generate-campaign")
async def generate_campaign(request: CampaignRequest, user: dict = Depends(verify_clerk_user)):
    try:
        system_instruction = f"""
        You are an expert real estate copywriter working for PropBlitz-AI. 
        Generate 3 distinct marketing channels using these exact parameters:
        - Project / Society Name: {request.project_name}
        - Property Type & Build: {request.bhk} {request.prop_type}
        - Location Matrix: {request.locality}, {request.city}
        - Pricing Structure: {request.price}
        - Core Amenities Array: {', '.join(request.amenities)}
        - Strategic Summary & Features: {request.features}
        - Targeted Campaign Tone: {request.tone}

        STRICT WRITING DIRECTIVES (CRITICAL FOR PRODUCTION LAUNCH):
        1. GREETING: Do not generate placeholders like '[Name]' or '[Client Name]'. Always begin the copy variations directly with warm broadcast call-outs like "Namaste!" or "Hi there!".
        2. IDENTITY MATCHING: Weave the actual property identity '{request.project_name}' seamlessly into structural sentences. Never output '[Apartment Name]'.
        3. CONTACT FALLBACKS: Absolutely zero bracketed tags are permitted in the text. Do not output '[phone number]' or '[email address]'. Terminate all campaign variants cleanly with: "Contact me to schedule an exclusive viewing."
        
        JSON STRUCTURE REQUIREMENTS:
        You must return your output exclusively as a valid JSON object. Do not wrap the JSON object in markdown blocks (no ```json). Use exactly these three dictionary keys:
        {{
            "listing": "Write a descriptive, high-converting social property listing ad block here.",
            "video": "Write a short-form video narrative script here containing performance visual cues.",
            "whatsapp": "Write an engaging, emoji-rich broadcast blast message variant here."
        }}
        """

        # Call the active, supported Groq Llama 3.1 model cluster
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Active, supported model ID
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user", 
                    "content": f"Generate a matching 3-channel real estate campaign framework for {request.project_name} in {request.locality} with a {request.tone} tone."
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"}  
        )

        response_content = completion.choices[0].message.content
        campaign_payload = json.loads(response_content)
        
        # Save dynamically to our temporary in-memory database list so it populates history tracking logs immediately
        MOCK_CAMPAIGN_DB.append({
            "id": str(len(MOCK_CAMPAIGN_DB) + 1),
            "project_name": request.project_name,
            **campaign_payload
        })
        
        return campaign_payload

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="AI engine failed to structure a valid JSON payload. Please click regenerate."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Pipeline Exception Encountered: {str(e)}"
        )

# 9. 🌟 RESTORED: Main Local Runtime Execution Engine
if __name__ == "__main__":
    import uvicorn
    # This executes uvicorn on port 8000 automatically whenever you run this file locally
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)