"""
GNews API Client.
Handles fetching trending news articles.
"""

import httpx
from typing import List, Dict, Any
from datetime import datetime, timezone

from trends.logger import get_logger

logger = get_logger(__name__)


class NewsClient:
    """Wrapper around GNews API client."""
    
    def __init__(self, api_key: str, api_base_url: str = "https://gnews.io/api/v4/"):
        """
        Initialize News client.
        
        Args:
            api_key: GNews API key
            api_base_url: GNews API base URL
        """
        self.api_key = api_key
        self.api_base_url = api_base_url.rstrip("/")
        logger.info("News client initialized")
    
    async def get_trending_articles(
        self,
        limit: int = 10,
        country: str = "us",
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Fetch trending news articles from GNews.
        
        Args:
            limit: Number of articles to fetch (max 10 for free tier)
            country: Country code (us, in, gb, etc.)
            language: Language code (en, etc.)
        
        Returns:
            List of article dictionaries with metadata
        """
        try:
            url = f"{self.api_base_url}/top-headlines"
            params = {
                "apikey": self.api_key,
                "lang": language,
                "country": country,
                "max": min(limit, 10)  # GNews free tier limit
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            if not data or not data.get("articles"):
                logger.warning("No articles found in GNews response")
                return []
            
            trend_items = []
            for article in data["articles"][:limit]:
                try:
                    # Parse published date
                    published_at_str = article.get("publishedAt")
                    if published_at_str:
                        published_at = datetime.fromisoformat(
                            published_at_str.replace("Z", "+00:00")
                        )
                    else:
                        published_at = datetime.now(timezone.utc)
                    
                    # Calculate engagement score (use views/clicks if available, otherwise use 0)
                    # For news, we'll use a simple score based on recency and source
                    engagement_score = 100.0  # Base score for news articles
                    
                    trend_item = {
                        "title": article.get("title", "No Title"),
                        "description": article.get("description", article.get("content", ""))[:500],
                        "url": article.get("url", "#"),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "score": 0,  # News doesn't have upvotes
                        "upvote_ratio": None,
                        "num_comments": 0,  # News doesn't have comments
                        "created_utc": published_at,
                        "author": None,  # GNews doesn't always provide author
                        "flair": None,
                        "is_nsfw": False,
                        "engagement_score": engagement_score
                    }
                    trend_items.append(trend_item)
                except Exception as e:
                    logger.error(f"Error processing article: {e}", exc_info=True)
                    continue
            
            logger.info(f"Fetched {len(trend_items)} trending news articles")
            return trend_items
            
        except Exception as e:
            logger.error(f"Error fetching news trends: {e}", exc_info=True)
            raise

