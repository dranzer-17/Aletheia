"""
FastAPI router for trends endpoints.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional

from database import db
from trends.schema import TrendResponse, TrendDocument
from trends.reddit.reddit_client import RedditClient
from trends.reddit.reddit_fetcher import RedditFetcher
from config import (
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT,
    GNEWS_API_KEY, GNEWS_API_BASE_URL,
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_PATH
)
from trends.news.news_client import NewsClient
from trends.news.news_fetcher import NewsFetcher
from trends.telegram.telegram_fetcher import TelegramFetcher
from trends.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("/reddit", response_model=TrendResponse)
async def get_reddit_trends(
    force_refresh: bool = False
):
    """
    Get Reddit trends.
    
    - Returns cached data if available and not expired
    - If expired or force_refresh=True, fetches fresh data from Reddit API
    - Returns top 10 trending posts from r/all
    """
    try:
        reddit_client = RedditClient(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        
        fetcher = RedditFetcher(reddit_client, update_frequency_minutes=30)
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = await fetcher.get_cached_trends()
            if cached:
                logger.info("Returning cached Reddit trends")
                return TrendResponse(
                    **cached.model_dump(),
                    is_cached=True
                )
        
        # Fetch fresh data
        logger.info("Fetching fresh Reddit trends from API")
        trend_doc = await fetcher.fetch_and_store(
            subreddit_source="all",
            limit=10,
            sort_method="hot"
        )
        
        return TrendResponse(
            **trend_doc.model_dump(),
            is_cached=False
        )
        
    except Exception as e:
        logger.error(f"Error fetching Reddit trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Reddit trends: {str(e)}"
        )


@router.get("/reddit/status")
async def get_reddit_status():
    """Get status of Reddit trends (last fetch time, cache status)."""
    try:
        doc = await db.trends.find_one({"platform": "reddit"})
        
        if not doc:
            return {
                "platform": "reddit",
                "status": "no_data",
                "message": "No trends data available yet. First fetch will happen automatically."
            }
        
        from datetime import datetime, timezone
        expires_at = doc.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            is_expired = datetime.now(timezone.utc) > expires_at
        
        return {
            "platform": "reddit",
            "status": "expired" if is_expired else "cached",
            "fetch_timestamp": doc.get("fetch_timestamp"),
            "expires_at": expires_at,
            "trends_count": len(doc.get("trends", [])),
            "update_frequency_minutes": doc.get("update_frequency_minutes", 30)
        }
        
    except Exception as e:
        logger.error(f"Error getting Reddit status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("/news", response_model=TrendResponse)
async def get_news_trends(
    force_refresh: bool = False
):
    """
    Get news trends from GNews.
    
    - Returns cached data if available and fetched today
    - If not fetched today or force_refresh=True, fetches fresh data from GNews API
    - Returns top 10 trending news articles
    """
    try:
        news_client = NewsClient(
            api_key=GNEWS_API_KEY,
            api_base_url=GNEWS_API_BASE_URL
        )
        
        fetcher = NewsFetcher(news_client, update_frequency_hours=24)
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = await fetcher.get_cached_trends()
            if cached:
                logger.info("Returning cached news trends")
                return TrendResponse(
                    **cached.model_dump(),
                    is_cached=True
                )
        
        # Fetch fresh data
        logger.info("Fetching fresh news trends from API")
        trend_doc = await fetcher.fetch_and_store(
            limit=10,
            country="us",
            language="en"
        )
        
        return TrendResponse(
            **trend_doc.model_dump(),
            is_cached=False
        )
        
    except Exception as e:
        logger.error(f"Error fetching news trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch news trends: {str(e)}"
        )


@router.get("/news/status")
async def get_news_status():
    """Get status of news trends (last fetch time, cache status)."""
    try:
        doc = await db.trends.find_one({"platform": "news"})
        
        if not doc:
            return {
                "platform": "news",
                "status": "no_data",
                "message": "No trends data available yet. First fetch will happen automatically."
            }
        
        from datetime import datetime, timezone
        fetch_timestamp = doc.get("fetch_timestamp")
        is_expired = True  # Default to expired if no timestamp
        
        if fetch_timestamp:
            if isinstance(fetch_timestamp, str):
                fetch_timestamp = datetime.fromisoformat(fetch_timestamp.replace("Z", "+00:00"))
            elif fetch_timestamp.tzinfo is None:
                fetch_timestamp = fetch_timestamp.replace(tzinfo=timezone.utc)
            
            # Check if fetched today
            now = datetime.now(timezone.utc)
            is_expired = fetch_timestamp.date() < now.date()
        
        return {
            "platform": "news",
            "status": "expired" if is_expired else "cached",
            "fetch_timestamp": doc.get("fetch_timestamp"),
            "trends_count": len(doc.get("trends", [])),
            "update_frequency_hours": 24
        }
        
    except Exception as e:
        logger.error(f"Error getting news status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("/telegram", response_model=TrendResponse)
async def get_telegram_trends(force_refresh: bool = False):
    """
    Get Telegram trends.

    - Returns cached data if available and not expired
    - If expired or force_refresh=True, fetches fresh data from Telegram channels
    - Returns top 10 posts ranked by engagement
    """
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram credentials are not configured",
        )

    try:
        fetcher = TelegramFetcher(update_frequency_minutes=30)

        if not force_refresh:
            cached = await fetcher.get_cached_trends()
            if cached:
                logger.info("Returning cached Telegram trends")
                return TrendResponse(
                    **cached.model_dump(),
                    is_cached=True
                )

        logger.info("Fetching fresh Telegram trends from API")
        trend_doc = await fetcher.fetch_and_store(limit=10, per_channel_limit=25)

        return TrendResponse(
            **trend_doc.model_dump(),
            is_cached=False
        )

    except Exception as e:
        logger.error(f"Error fetching Telegram trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Telegram trends: {str(e)}"
        )


@router.get("/telegram/status")
async def get_telegram_status():
    """Get status of Telegram trends (last fetch time, cache status)."""
    try:
        doc = await db.trends.find_one({"platform": "telegram"})

        if not doc:
            return {
                "platform": "telegram",
                "status": "no_data",
                "message": "No trends data available yet. First fetch will happen automatically."
            }

        from datetime import datetime, timezone
        expires_at = doc.get("expires_at")
        is_expired = True
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            is_expired = datetime.now(timezone.utc) > expires_at

        return {
            "platform": "telegram",
            "status": "expired" if is_expired else "cached",
            "fetch_timestamp": doc.get("fetch_timestamp"),
            "expires_at": expires_at,
            "trends_count": len(doc.get("trends", [])),
            "update_frequency_minutes": 30
        }

    except Exception as e:
        logger.error(f"Error getting Telegram status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )

