"""
APScheduler setup for periodic trend updates.
"""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timedelta

from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    GNEWS_API_KEY,
    GNEWS_API_BASE_URL,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION_PATH,
)
from trends.reddit.reddit_client import RedditClient
from trends.reddit.reddit_fetcher import RedditFetcher
from trends.news.news_client import NewsClient
from trends.news.news_fetcher import NewsFetcher
from trends.telegram.telegram_fetcher import TelegramFetcher
from trends.logger import get_logger

logger = get_logger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


async def fetch_reddit_trends_job(force: bool = False):
    """
    Scheduled job to fetch and store Reddit trends.
    
    Args:
        force: If True, fetch even if valid cache exists. If False, check cache first.
    """
    try:
        reddit_client = RedditClient(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        
        fetcher = RedditFetcher(reddit_client, update_frequency_minutes=30)
        
        # Check cache first unless forced
        if not force:
            cached = await fetcher.get_cached_trends()
            if cached:
                logger.info(f"Valid cached Reddit trends found (expires at {cached.expires_at}), skipping fetch")
                return
        
        logger.info("Running scheduled Reddit trends fetch")
        await fetcher.fetch_and_store(
            subreddit_source="all",
            limit=10,
            sort_method="hot"
        )
        
        logger.info("Scheduled Reddit trends fetch completed")
    except Exception as e:
        logger.error(f"Error in scheduled Reddit trends fetch: {e}", exc_info=True)


async def fetch_news_trends_job(force: bool = False):
    """
    Scheduled job to fetch and store news trends.
    
    Args:
        force: If True, fetch even if valid cache exists. If False, check cache first.
    """
    try:
        news_client = NewsClient(
            api_key=GNEWS_API_KEY,
            api_base_url=GNEWS_API_BASE_URL
        )
        
        fetcher = NewsFetcher(news_client, update_frequency_hours=24)
        
        # Check cache first unless forced
        if not force:
            cached = await fetcher.get_cached_trends()
            if cached:
                logger.info(f"Valid cached news trends found (fetched today), skipping fetch")
                return
        
        logger.info("Running scheduled news trends fetch")
        await fetcher.fetch_and_store(
            limit=10,
            country="us",
            language="en"
        )
        
        logger.info("Scheduled news trends fetch completed")
    except Exception as e:
        logger.error(f"Error in scheduled news trends fetch: {e}", exc_info=True)


async def fetch_telegram_trends_job(force: bool = False):
    """
    Scheduled job to fetch and store Telegram trends.

    Args:
        force: If True, fetch even if valid cache exists. If False, check cache first.
    """
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.warning("Telegram credentials not configured; skipping Telegram trends job")
        return

    try:
        fetcher = TelegramFetcher(update_frequency_minutes=30)

        # Check cache first unless forced
        if not force:
            cached = await fetcher.get_cached_trends()
            if cached:
                logger.info(
                    "Valid cached Telegram trends found (expires at %s), skipping fetch",
                    cached.expires_at,
                )
                return

        logger.info("Running scheduled Telegram trends fetch")
        await fetcher.fetch_and_store(limit=10, per_channel_limit=25)

        logger.info("Scheduled Telegram trends fetch completed")
    except Exception as e:
        logger.error(f"Error in scheduled Telegram trends fetch: {e}", exc_info=True)


def setup_scheduler():
    """Setup and start the scheduler."""
    # Reddit: every 30 minutes
    scheduler.add_job(
        fetch_reddit_trends_job,
        trigger=IntervalTrigger(minutes=30),
        id="reddit_trends",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping jobs
        coalesce=True,  # Combine multiple pending executions into one
        misfire_grace_time=60  # Grace period for missed jobs
    )
    
    # News: every 24 hours (once per day)
    scheduler.add_job(
        fetch_news_trends_job,
        trigger=IntervalTrigger(hours=24),
        id="news_trends",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping jobs
        coalesce=True,  # Combine multiple pending executions into one
        misfire_grace_time=3600  # Grace period for missed jobs (1 hour)
    )

    # Telegram: every 30 minutes
    scheduler.add_job(
        fetch_telegram_trends_job,
        trigger=IntervalTrigger(minutes=30),
        id="telegram_trends",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    
    logger.info(
        "Trends scheduler configured: Reddit/Telegram every 30 minutes, News every 24 hours"
    )
    
    # Start scheduler
    scheduler.start()
    logger.info("Trends scheduler started")
    
    # Trigger initial fetch only if cache is missing or expired (non-blocking)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule the tasks (will check cache first)
            asyncio.create_task(fetch_reddit_trends_job(force=False))
            asyncio.create_task(fetch_news_trends_job(force=False))
            asyncio.create_task(fetch_telegram_trends_job(force=False))
        else:
            # If no loop, create one and run (will check cache first)
            loop.run_until_complete(asyncio.gather(
                fetch_reddit_trends_job(force=False),
                fetch_news_trends_job(force=False),
                fetch_telegram_trends_job(force=False),
            ))
    except RuntimeError:
        # No event loop exists, scheduler will handle it
        logger.info("Event loop not available, scheduler will trigger first fetch")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    scheduler.shutdown()
    logger.info("Trends scheduler shut down")

