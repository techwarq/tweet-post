# routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from twitter_tool import TwitterTool
from langchain_groq import ChatGroq
import os

# Initialize router
router = APIRouter()

# Initialize the Twitter tool
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
DATA_DIR = os.getenv("DATA_DIR", "data")

# Create LLM instance
llm = ChatGroq(
    temperature=0.7,
    model_name="llama3-70b-8192",
    api_key=GROQ_API_KEY
)

# Initialize the TwitterTool
twitter_tool = TwitterTool(
    api_key=TAVILY_API_KEY,
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
async def scrape_profile(request: ScrapeProfileRequest):
    """Scrape a Twitter profile and analyze the tweets."""
    if not request.username:
        raise HTTPException(status_code=400, detail="Username is required")
    
    result = twitter_tool.scrape_profile(request.username)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
    
    return result

@router.post("/generate-post/{username}")
async def generate_post(username: str, request: GeneratePostRequest):
    """Generate a post based on a Twitter profile and optional user info."""
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