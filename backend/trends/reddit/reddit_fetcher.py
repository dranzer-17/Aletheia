"""
Reddit Fetcher: Fetches trends from Reddit API and stores in MongoDB.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from database import db
from trends.schema import TrendDocument, TrendItem
from trends.reddit.reddit_client import RedditClient
from trends.logger import get_logger

logger = get_logger(__name__)


class RedditFetcher:
    """Handles fetching and storing Reddit trends."""
    
    def __init__(self, reddit_client: RedditClient, update_frequency_minutes: int = 30):
        """
        Initialize Reddit fetcher.
        
        Args:
            reddit_client: RedditClient instance
            update_frequency_minutes: How often to update (default 30)
        """
        self.reddit_client = reddit_client
        self.update_frequency_minutes = update_frequency_minutes
        self.platform = "reddit"
    
    async def fetch_and_store(
        self,
        subreddit_source: str = "all",
        limit: int = 10,
        sort_method: str = "hot"
    ) -> TrendDocument:
        """
        Fetch trends from Reddit and store in MongoDB.
        Overwrites existing document for this platform.
        
        Args:
            subreddit_source: Subreddit to fetch from
            limit: Number of posts to fetch
            sort_method: Sort method (hot, top, rising, etc.)
        
        Returns:
            TrendDocument with fetched data
        """
        logger.info(f"Fetching Reddit trends from r/{subreddit_source}")
        
        # Fetch from Reddit API
        trend_items_data = self.reddit_client.get_trending_posts(
            subreddit_source=subreddit_source,
            limit=limit,
            sort_method=sort_method
        )
        
        # Convert to TrendItem objects
        trend_items = [TrendItem(**item) for item in trend_items_data]
        
        # Create document
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.update_frequency_minutes)
        
        trend_doc = TrendDocument(
            platform=self.platform,
            fetch_timestamp=now,
            update_frequency_minutes=self.update_frequency_minutes,
            trends=trend_items,
            expires_at=expires_at
        )
        
        # Upsert to MongoDB (overwrite if exists)
        await db.trends.update_one(
            {"platform": self.platform},
            {"$set": trend_doc.model_dump()},
            upsert=True
        )
        
        logger.info(f"Stored {len(trend_items)} Reddit trends in MongoDB")
        return trend_doc
    
    async def get_cached_trends(self) -> Optional[TrendDocument]:
        """
        Get cached trends from MongoDB if they exist and are not expired.
        
        Returns:
            TrendDocument if valid cache exists, None otherwise
        """
        doc = await db.trends.find_one({"platform": self.platform})
        
        if not doc:
            return None
        
        # Check if expired
        expires_at = doc.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if datetime.now(timezone.utc) > expires_at:
                logger.info("Cached Reddit trends expired")
                return None
        
        # Convert to TrendDocument
        try:
            return TrendDocument(**doc)
        except Exception as e:
            logger.error(f"Error parsing cached trends: {e}", exc_info=True)
            return None

