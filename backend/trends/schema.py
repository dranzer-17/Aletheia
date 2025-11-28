from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    """Individual trend item from a platform."""
    title: str = Field(..., description="Title of the trend")
    description: str = Field(..., description="Description or content")
    url: str = Field(..., description="URL to the original post/content")
    source: str = Field(..., description="Source identifier (e.g., subreddit name)")
    score: int = Field(..., description="Upvotes/score")
    upvote_ratio: Optional[float] = Field(None, description="Upvote ratio (0-1)")
    num_comments: int = Field(..., description="Number of comments")
    created_utc: datetime = Field(..., description="Creation timestamp")
    author: Optional[str] = Field(None, description="Author username")
    flair: Optional[str] = Field(None, description="Flair/tag")
    is_nsfw: bool = Field(False, description="NSFW flag")
    engagement_score: float = Field(..., description="Calculated engagement: score * comments")


class TrendDocument(BaseModel):
    """MongoDB document structure for trends collection."""
    platform: str = Field(..., description="Platform name (reddit, telegram, etc.)")
    fetch_timestamp: datetime = Field(..., description="When data was fetched from API")
    update_frequency_minutes: int = Field(..., description="Update frequency in minutes")
    trends: List[TrendItem] = Field(..., description="List of trend items")
    expires_at: datetime = Field(..., description="Expiration timestamp")


class TrendResponse(BaseModel):
    """API response model for trends."""
    platform: str
    fetch_timestamp: datetime
    update_frequency_minutes: int
    trends: List[TrendItem]
    expires_at: datetime
    is_cached: bool = Field(False, description="Whether data came from cache")


class TrendFilterRequest(BaseModel):
    """Optional filters for trends (handled in frontend, but can be used for API)."""
    keyword: Optional[str] = None
    subreddit: Optional[str] = None
    min_score: Optional[int] = None
    min_comments: Optional[int] = None
    sort_by: Optional[str] = Field(None, description="score, comments, engagement_score, timestamp")
    sort_order: Optional[str] = Field("desc", description="asc or desc")

