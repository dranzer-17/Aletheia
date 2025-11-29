"""FastAPI router for globe endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List

from auth.router import get_current_user
from globe.schema import LocationNewsRequest, LocationNewsResponse, LocationInfo, NewsArticle
from globe.geocoder import reverse_geocode
from globe.news_fetcher import fetch_news_by_location, format_news_article
from logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/globe", tags=["globe"])


@router.post("/news", response_model=LocationNewsResponse, status_code=status.HTTP_200_OK)
async def get_location_news(
    request: LocationNewsRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Get top trending news for a location based on latitude and longitude.
    
    Priority: city -> state -> country
    """
    try:
        logger.info(f"Fetching news for location: {request.latitude}, {request.longitude}")
        
        # Step 1: Reverse geocode to get location information
        location_data = reverse_geocode(request.latitude, request.longitude)
        if not location_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not determine location from provided coordinates.",
            )
        location_info = LocationInfo(**location_data)
        
        # Step 2: Fetch news with priority: city -> state -> country
        articles_raw = fetch_news_by_location(
            city=location_info.city,
            state=location_info.state,
            country_code=location_info.country_code,
            limit=request.limit,
        )
        
        # Step 3: Format articles
        articles = [NewsArticle(**format_news_article(article)) for article in articles_raw]
        
        # Determine which location level was used
        search_priority = "country"  # Default fallback
        if location_info.city and any(
            location_info.city.lower() in article.title.lower() 
            or location_info.city.lower() in article.description.lower()
            for article in articles
        ):
            search_priority = "city"
        elif location_info.state and any(
            location_info.state.lower() in article.title.lower() 
            or location_info.state.lower() in article.description.lower()
            for article in articles
        ):
            search_priority = "state"
        
        logger.info(
            f"Returning {len(articles)} articles for location "
            f"(City: {location_info.city}, State: {location_info.state}, Country: {location_info.country})"
        )
        
        return LocationNewsResponse(
            location=location_info,
            articles=articles,
            total_count=len(articles),
            search_priority=search_priority,
        )
        
    except Exception as e:
        logger.error(f"Error fetching location news: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch news for location: {str(e)}",
        )

