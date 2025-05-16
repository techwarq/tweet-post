# routes.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional
from twitter_tool import TwitterTool
from langchain_groq import ChatGroq
import os
from fastapi.responses import JSONResponse

# Initialize router
router = APIRouter()

# Initialize the Twitter tool
GROQ_API_KEY = "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"
DATA_DIR = os.getenv("DATA_DIR", "data")

# Create LLM instance
llm = ChatGroq(
    temperature=0.7,
    model_name="llama3-70b-8192",
    api_key=GROQ_API_KEY
)

# Initialize the TwitterTool (no need for API key since we're using CLI)
twitter_tool = TwitterTool(
    llm=llm,
    data_dir=DATA_DIR
)

# Define request models
class ScrapeProfileRequest(BaseModel):
    username: str

class GeneratePostRequest(BaseModel):
    topic: str
    length: str = "Medium"
    style: Optional[str] = None
    include_hashtags: bool = True
    include_cta: bool = False
    user_id: Optional[str] = None

class SaveUserInfoRequest(BaseModel):
    user_info: Dict[str, Any]

# Define routes
@router.get("/")
async def root():
    return {"message": "Twitter Post Generator API is running"}

@router.post("/scrape-profile")
async def scrape_profile(request: Request):
    """Scrape a Twitter profile and analyze the tweets."""
    data = await request.json()
    result = await twitter_tool.scrape_profile(data["username"])
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
    return JSONResponse(result)

@router.post("/generate-post/{username}")
async def generate_post(username: str, request: GeneratePostRequest):
    """Generate a post based on a Twitter profile and optional user info."""
    # Remove @ symbol if present
    username = username.strip("@")
    
    tweets = twitter_tool.load_data(username, "tweets")
    
    if not tweets:
        raise HTTPException(
            status_code=404, 
            detail=f"No data found for @{username}. Please scrape the profile first."
        )
    
    result = twitter_tool.generate_post(
        username=username,
        topic=request.topic,
        length=request.length,
        user_id=request.user_id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500, 
            detail=result.get("message", "Failed to generate post")
        )
    
    return result

@router.post("/save-user-info/{user_id}")
async def save_user_info(user_id: str, request: SaveUserInfoRequest):
    """Save user information for personalized tweet generation."""
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    
    result = twitter_tool.save_user_info(user_id, request.user_info)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
    
    return result

@router.get("/get-user-info/{user_id}")
async def get_user_info(user_id: str):
    """Get saved user information."""
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    
    result = twitter_tool.get_user_info(user_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "User information not found"))
    
    return result