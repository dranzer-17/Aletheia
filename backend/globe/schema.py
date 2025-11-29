"""Pydantic schemas for globee API."""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class LocationInfo(BaseModel):
    """Location information from geocoding."""
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None


class NewsArticle(BaseModel):
    """Formatted news article."""
    article_id: Optional[str] = None
    title: str
    description: str
    content: str = ""
    link: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    source_name: str
    source_url: Optional[str] = None
    source_icon: Optional[str] = None
    pub_date: Optional[str] = None
    pub_date_tz: Optional[str] = None
    language: Optional[str] = None
    country: List[str] = Field(default_factory=list)
    category: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    creator: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None
    sentiment_stats: Optional[Dict[str, Any]] = None
    ai_tag: List[str] = Field(default_factory=list)
    ai_region: List[str] = Field(default_factory=list)
    ai_org: List[str] = Field(default_factory=list)
    ai_summary: Optional[str] = None


class LocationNewsRequest(BaseModel):
    """Request model for location-based news."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate (-90 to 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate (-180 to 180)")
    limit: int = Field(default=10, ge=1, le=50, description="Number of articles to return (1-50)")


class LocationNewsResponse(BaseModel):
    """Response model for location-based news."""
    location: LocationInfo
    articles: List[NewsArticle]
    total_count: int
    search_priority: str = Field(description="Which location level was used: city, state, or country")

