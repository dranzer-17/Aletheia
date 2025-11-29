"""News fetcher using GNews API."""

from __future__ import annotations

from typing import List, Optional, Dict, Any
import httpx
from datetime import datetime

from config import GNEWS_API_KEY, GNEWS_API_BASE_URL
from logger import get_logger

logger = get_logger(__name__)

GNEWS_BASE_URL = GNEWS_API_BASE_URL.rstrip("/")


def fetch_news_by_location(
    city: Optional[str] = None,
    state: Optional[str] = None,
    country_code: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch news from GNews API based on location.
    
    Priority: city -> state -> country
    
    Args:
        city: City name (optional)
        state: State/region name (optional)
        country_code: ISO 3166-1 alpha-2 country code (optional)
        limit: Maximum number of articles to return (default: 10, max: 10 for free tier)
    
    Returns:
        List of news articles
    """
    if not GNEWS_API_KEY:
        raise RuntimeError("GNEWS_API_KEY is not configured")
    
    # GNews free tier limit is 10
    if limit > 10:
        limit = 10
    if limit < 1:
        limit = 10
    
    articles = []
    
    # Priority 1: Try city with country filter for better relevance
    if city and country_code:
        try:
            logger.info(f"Fetching news for city: {city} in country: {country_code}")
            articles = _fetch_news_gnews(query=city, country=country_code, limit=limit)
            if articles and len(articles) >= limit:
                logger.info(f"Found {len(articles)} articles for city {city}")
                return articles[:limit]
        except Exception as e:
            logger.warning(f"Failed to fetch news for city {city}: {e}")
    
    # Priority 2: Try city alone (without country filter)
    if city and not articles:
        try:
            logger.info(f"Fetching news for city: {city}")
            articles = _fetch_news_gnews(query=city, limit=limit)
            if articles and len(articles) >= limit:
                logger.info(f"Found {len(articles)} articles for city {city}")
                return articles[:limit]
        except Exception as e:
            logger.warning(f"Failed to fetch news for city {city}: {e}")
    
    # Priority 3: Try state with country filter
    if state and country_code and not articles:
        try:
            logger.info(f"Fetching news for state: {state} in country: {country_code}")
            articles = _fetch_news_gnews(query=state, country=country_code, limit=limit)
            if articles and len(articles) >= limit:
                logger.info(f"Found {len(articles)} articles for state {state}")
                return articles[:limit]
        except Exception as e:
            logger.warning(f"Failed to fetch news for state {state}: {e}")
    
    # Priority 4: Try state alone
    if state and not articles:
        try:
            logger.info(f"Fetching news for state: {state}")
            articles = _fetch_news_gnews(query=state, limit=limit)
            if articles and len(articles) >= limit:
                logger.info(f"Found {len(articles)} articles for state {state}")
                return articles[:limit]
        except Exception as e:
            logger.warning(f"Failed to fetch news for state {state}: {e}")
    
    # Priority 5: Fall back to country
    if country_code and not articles:
        try:
            logger.info(f"Fetching news for country: {country_code}")
            articles = _fetch_news_gnews(country=country_code, limit=limit)
            if articles:
                logger.info(f"Found {len(articles)} articles for country {country_code}")
                return articles[:limit]
        except Exception as e:
            logger.warning(f"Failed to fetch news for country {country_code}: {e}")
    
    # If all else fails, return what we have or empty list
    if articles:
        logger.info(f"Returning {len(articles)} articles (less than requested {limit})")
        return articles[:limit]
    
    logger.warning("No news found for any location level")
    return []


def _fetch_news_gnews(
    query: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Internal function to fetch news from GNews API.
    
    Args:
        query: Search query (city, state, etc.)
        country: Country code (ISO 3166-1 alpha-2)
        limit: Maximum number of articles (max 10 for free tier)
    
    Returns:
        List of raw article dictionaries from GNews
    """
    try:
        url = f"{GNEWS_BASE_URL}/search"
        params = {
            "apikey": GNEWS_API_KEY,
            "lang": "en",
            "max": min(limit, 10),
        }
        
        if query:
            params["q"] = query
        
        if country:
            params["country"] = country.lower()
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data or not data.get("articles"):
                logger.warning("No articles found in GNews response")
                return []
            
            results = data.get("articles", [])
            logger.info(f"Fetched {len(results)} news articles from GNews")
            
            return results
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching news from GNews: {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        logger.error(f"Request error fetching news from GNews: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching news from GNews: {e}", exc_info=True)
        return []


def format_news_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a news article from GNews API response to a standardized format.
    
    Args:
        article: Raw article from GNews API
    
    Returns:
        Formatted article dictionary compatible with the schema
    """
    # Parse published date
    published_at_str = article.get("publishedAt")
    pub_date = None
    if published_at_str:
        try:
            # GNews uses ISO format like "2024-01-15T10:30:00Z"
            pub_date = published_at_str
        except Exception:
            pass
    
    # Extract source information
    source_info = article.get("source", {})
    source_name = source_info.get("name", "Unknown Source") if isinstance(source_info, dict) else "Unknown Source"
    
    # Get description or use content as fallback
    description = article.get("description") or article.get("content", "")[:500] or ""
    
    return {
        "article_id": None,  # GNews doesn't provide article IDs
        "title": article.get("title", "") or "No Title",
        "description": description,
        "content": article.get("content", "") or "",
        "link": article.get("url", "") or "#",
        "image_url": article.get("image"),
        "video_url": None,  # GNews doesn't provide video URLs in search results
        "source_name": source_name,
        "source_url": None,  # GNews doesn't provide source URLs
        "source_icon": None,  # GNews doesn't provide source icons
        "pub_date": pub_date,
        "pub_date_tz": None,  # GNews doesn't provide timezone info separately
        "language": article.get("language", "en") or "en",
        "country": [],  # GNews doesn't provide country list per article
        "category": [],  # GNews doesn't provide categories in search results
        "keywords": [],  # GNews doesn't provide keywords
        "creator": [],  # GNews doesn't provide creator information
        "sentiment": None,  # GNews doesn't provide sentiment analysis
        "sentiment_stats": None,  # GNews doesn't provide sentiment stats
        "ai_tag": [],  # GNews doesn't provide AI tags
        "ai_region": [],  # GNews doesn't provide AI regions
        "ai_org": [],  # GNews doesn't provide AI orgs
        "ai_summary": None,  # GNews doesn't provide AI summary
    }

