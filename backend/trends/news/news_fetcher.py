"""
News Fetcher: Fetches trends from GNews API and stores in MongoDB.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from database import db
from trends.schema import TrendDocument, TrendItem
from trends.news.news_client import NewsClient
from trends.logger import get_logger

logger = get_logger(__name__)


class NewsFetcher:
    """Handles fetching and storing news trends."""
    
    def __init__(self, news_client: NewsClient, update_frequency_hours: int = 24):
        """
        Initialize News fetcher.
        
        Args:
            news_client: NewsClient instance
            update_frequency_hours: How often to update (default 24 hours)
        """
        self.news_client = news_client
        self.update_frequency_hours = update_frequency_hours
        self.platform = "news"
    
    async def fetch_and_store(
        self,
        limit: int = 10,
        country: str = "us",
        language: str = "en"
    ) -> TrendDocument:
        """
        Fetch trends from GNews and store in MongoDB.
        Overwrites existing document for this platform.
        
        Args:
            limit: Number of articles to fetch
            country: Country code
            language: Language code
        
        Returns:
            TrendDocument with fetched data
        """
        logger.info(f"Fetching news trends (limit: {limit})")
        
        # Fetch from GNews API
        trend_items_data = await self.news_client.get_trending_articles(
            limit=limit,
            country=country,
            language=language
        )
        
        # Convert to TrendItem objects
        trend_items = [TrendItem(**item) for item in trend_items_data]
        
        # Create document
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.update_frequency_hours)
        
        trend_doc = TrendDocument(
            platform=self.platform,
            fetch_timestamp=now,
            update_frequency_minutes=self.update_frequency_hours * 60,  # Convert to minutes for consistency
            trends=trend_items,
            expires_at=expires_at
        )
        
        # Upsert to MongoDB (overwrite if exists)
        await db.trends.update_one(
            {"platform": self.platform},
            {"$set": trend_doc.model_dump()},
            upsert=True
        )
        
        logger.info(f"Stored {len(trend_items)} news trends in MongoDB")
        return trend_doc
    
    async def get_cached_trends(self) -> Optional[TrendDocument]:
        """
        Get cached trends from MongoDB if they exist and were fetched today.
        
        Returns:
            TrendDocument if valid cache exists (fetched today), None otherwise
        """
        doc = await db.trends.find_one({"platform": self.platform})
        
        if not doc:
            return None
        
        # Check if fetched today (not expired)
        fetch_timestamp = doc.get("fetch_timestamp")
        if fetch_timestamp:
            if isinstance(fetch_timestamp, str):
                fetch_timestamp = datetime.fromisoformat(fetch_timestamp.replace("Z", "+00:00"))
            elif fetch_timestamp.tzinfo is None:
                fetch_timestamp = fetch_timestamp.replace(tzinfo=timezone.utc)
            
            # Check if fetched today (same day in UTC)
            now = datetime.now(timezone.utc)
            if fetch_timestamp.date() < now.date():
                logger.info("Cached news trends expired (not from today)")
                return None
        
        # Convert to TrendDocument
        try:
            return TrendDocument(**doc)
        except Exception as e:
            logger.error(f"Error parsing cached trends: {e}", exc_info=True)
            return None

