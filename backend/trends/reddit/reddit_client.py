"""
Reddit API Client using PRAW.
Handles authentication and fetching trending posts.
"""

import praw
from typing import List, Dict, Any
from datetime import datetime, timezone

from trends.logger import get_logger

logger = get_logger(__name__)


class RedditClient:
    """Wrapper around PRAW Reddit API client."""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """
        Initialize Reddit client.
        
        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string (required by Reddit API)
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        logger.info("Reddit client initialized")
    
    def get_trending_posts(
        self,
        subreddit_source: str = "all",
        limit: int = 30,
        sort_method: str = "hot"
    ) -> List[Dict[str, Any]]:
        """
        Fetch trending posts from Reddit.
        
        Args:
            subreddit_source: Subreddit to fetch from (all, popular, india, etc.)
            limit: Number of posts to fetch (max 100)
            sort_method: hot, top, rising, new, controversial
        
        Returns:
            List of post dictionaries with metadata
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_source)
            
            # Get posts based on sort method
            if sort_method == "hot":
                posts = subreddit.hot(limit=limit)
            elif sort_method == "top":
                posts = subreddit.top(limit=limit, time_filter="day")
            elif sort_method == "rising":
                posts = subreddit.rising(limit=limit)
            elif sort_method == "new":
                posts = subreddit.new(limit=limit)
            elif sort_method == "controversial":
                posts = subreddit.controversial(limit=limit, time_filter="day")
            else:
                logger.warning(f"Unknown sort method: {sort_method}, defaulting to hot")
                posts = subreddit.hot(limit=limit)
            
            trend_items = []
            for post in posts:
                try:
                    # Calculate engagement score
                    engagement_score = float(post.score * post.num_comments) if post.num_comments > 0 else float(post.score)
                    
                    trend_item = {
                        "title": post.title,
                        "description": post.selftext[:500] if post.selftext else post.url,  # Truncate long text
                        "url": f"https://reddit.com{post.permalink}",
                        "source": post.subreddit.display_name,
                        "score": post.score,
                        "upvote_ratio": post.upvote_ratio,
                        "num_comments": post.num_comments,
                        "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                        "author": str(post.author) if post.author else None,
                        "flair": post.link_flair_text,
                        "is_nsfw": post.over_18,
                        "engagement_score": engagement_score
                    }
                    trend_items.append(trend_item)
                except Exception as e:
                    logger.error(f"Error processing post {post.id}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Fetched {len(trend_items)} trending posts from r/{subreddit_source}")
            return trend_items
            
        except Exception as e:
            logger.error(f"Error fetching Reddit trends: {e}", exc_info=True)
            raise

