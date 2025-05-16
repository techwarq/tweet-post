"""Data models for the Twitter Post Generator API."""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class TwitterProfile(BaseModel):
    """Request model for scraping a Twitter profile."""
    username: str

class PostGenerationRequest(BaseModel):
    """Request model for generating a Twitter post."""
    topic: str = "General"
    length: str = "Medium"  # Short, Medium, Long

class EstimatedMetrics(BaseModel):
    """Estimated engagement metrics for a generated post."""
    likes: str
    retweets: str
    views: str

class GeneratedPost(BaseModel):
    """Response model for a generated Twitter post."""
    success: bool
    post: str
    hashtags: List[str] = []
    best_time: Optional[str] = None
    viral_elements: Union[List[str], str] = Field(default_factory=list)
    engagement_prediction: str
    estimated_metrics: Optional[EstimatedMetrics] = None
    error: Optional[str] = None
    
    class Config:
        # Allow extra fields
        extra = "allow"

class PerformanceAnalysis(BaseModel):
    """Model for tweet performance analysis."""
    content_patterns: List[str] = Field(default_factory=list)
    style_elements: List[str] = Field(default_factory=list)
    optimal_format: str = ""
    view_vs_engagement: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    success: bool = True
    
    class Config:
        # Allow extra fields
        extra = "allow"

class Tweet(BaseModel):
    """Model for a Twitter tweet."""
    text: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    views: int = 0
    engagement_score: int = 0
    url: Optional[str] = None
    date: Optional[str] = None
    user: Optional[str] = None
    is_retweet: bool = False
    is_quote: bool = False
    is_reply: bool = False
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    
    class Config:
        # Allow extra fields
        extra = "allow"

class ScrapeResult(BaseModel):
    """Response model for scraping a Twitter profile."""
    success: bool
    message: str
    tweet_count: Optional[int] = None
    top_tweets_count: Optional[int] = None
    performance_analysis: Optional[Union[PerformanceAnalysis, Dict[str, Any]]] = None
    sample_tweets: Optional[List[Tweet]] = None
    # For backward compatibility (app.py expects "tweets" key)
    tweets: Optional[List[Tweet]] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        # Copy sample_tweets to tweets for backward compatibility if needed
        if self.sample_tweets and not self.tweets:
            self.tweets = self.sample_tweets[:10]
    
    class Config:
        # Allow extra fields
        extra = "allow"

class ProfileInfo(BaseModel):
    """Model for Twitter profile information."""
    username: str
    followers: Union[str, int] = "N/A"
    following: Union[str, int] = "N/A"
    
    class Config:
        # Allow extra fields
        extra = "allow"

class UserInfoResponse(BaseModel):
    """Response model for user info operations."""
    success: bool
    message: str
    user_info: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"