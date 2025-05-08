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
    post: str
    hashtags: List[str] = []
    best_time: Optional[str] = None
    viral_elements: Union[List[str], str] = Field(default_factory=list)
    engagement_prediction: str
    estimated_metrics: Optional[EstimatedMetrics] = None
    
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
    views: int = 0
    engagement_score: int = 0
    url: Optional[str] = None
    is_viral: bool = False
    
    class Config:
        # Allow extra fields
        extra = "allow"

class ScrapeResult(BaseModel):
    """Response model for scraping a Twitter profile."""
    success: bool
    message: str
    tweet_count: Optional[int] = None
    performance_analysis: Optional[Union[PerformanceAnalysis, Dict[str, Any]]] = None
    tweets: Optional[List[Tweet]] = None
    
    class Config:
        # Allow extra fields
        extra = "allow"