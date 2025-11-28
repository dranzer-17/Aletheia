"""Telegram Fetcher: Fetches trends from Telegram channels and stores in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from telethon.tl.custom.message import Message

from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_PATH
from database import db
from trends.schema import TrendDocument, TrendItem
from trends.telegram.telegram_client import (
    TelegramClientManager,
    get_configured_channel_list,
    build_channel_priority_map,
)
from trends.logger import get_logger

logger = get_logger(__name__)


class TelegramFetcher:
    """Handles fetching and storing Telegram trends."""

    def __init__(self, update_frequency_minutes: int = 30):
        self.update_frequency_minutes = update_frequency_minutes
        self.platform = "telegram"

    async def fetch_and_store(
        self,
        limit: int = 10,
        per_channel_limit: int = 25,
        channels: Optional[List[str]] = None,
    ) -> TrendDocument:
        """Fetch trends from Telegram channels and store in MongoDB."""

        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            raise RuntimeError("Telegram API credentials are not configured")

        channels = channels or get_configured_channel_list()
        if not channels:
            raise RuntimeError("No Telegram channels configured")

        priority_map = build_channel_priority_map(channels)

        logger.info(
            "Fetching Telegram trends from %d channels (limit=%d)",
            len(channels),
            limit,
        )

        posts: List[dict] = []

        async with TelegramClientManager(
            api_id=int(TELEGRAM_API_ID),
            api_hash=TELEGRAM_API_HASH,
            session_path=TELEGRAM_SESSION_PATH,
        ) as client:
            for channel in channels:
                channel_handle = channel.lstrip("@")
                try:
                    entity = await client.get_entity(channel_handle)
                except Exception as exc:
                    logger.warning("Failed to resolve Telegram channel %s: %s", channel, exc)
                    continue

                channel_name = getattr(entity, "title", None) or channel_handle
                channel_username = getattr(entity, "username", None)
                async for message in client.iter_messages(
                    entity, limit=per_channel_limit
                ):
                    if not isinstance(message, Message):
                        continue
                    text = (message.message or message.raw_text or "").strip()
                    if not text:
                        continue

                    views = int(getattr(message, "views", 0) or 0)
                    forwards = int(getattr(message, "forwards", 0) or 0)
                    reactions_summary = getattr(message, "reactions", None)
                    reactions_total = 0
                    if reactions_summary and getattr(reactions_summary, "results", None):
                        reactions_total = sum(
                            int(getattr(res, "count", 0) or 0)
                            for res in reactions_summary.results
                        )

                    if views == 0 and forwards == 0 and reactions_total == 0:
                        continue

                    created_at = message.date
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    else:
                        created_at = created_at.astimezone(timezone.utc)

                    engagement_score = views + (forwards * 2) + reactions_total

                    url = (
                        f"https://t.me/{channel_username}/{message.id}"
                        if channel_username
                        else ""
                    )

                    posts.append(
                        {
                            "title": text[:120] + ("…" if len(text) > 120 else ""),
                            "description": text[:500],
                            "url": url,
                            "source": channel_name,
                            "score": views,
                            "num_comments": forwards,
                            "created_utc": created_at,
                            "author": channel_username,
                            "is_nsfw": False,
                            "engagement_score": engagement_score,
                            "_priority": priority_map.get(
                                channel_handle.lower(), len(channels)
                            ),
                        }
                    )

        if not posts:
            logger.warning("No Telegram posts collected")

        sorted_posts = sorted(
            posts,
            key=lambda item: (
                item["created_utc"],
                item["engagement_score"],
                -item["_priority"],
            ),
            reverse=True,
        )
        top_posts = sorted_posts[:limit]
        for post in top_posts:
            post.pop("_priority", None)
        trend_items = [TrendItem(**item) for item in top_posts]

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.update_frequency_minutes)

        trend_doc = TrendDocument(
            platform=self.platform,
            fetch_timestamp=now,
            update_frequency_minutes=self.update_frequency_minutes,
            trends=trend_items,
            expires_at=expires_at,
        )

        await db.trends.update_one(
            {"platform": self.platform},
            {"$set": trend_doc.model_dump()},
            upsert=True,
        )

        logger.info("Stored %d Telegram trends in MongoDB", len(trend_items))
        return trend_doc

    async def get_cached_trends(self) -> Optional[TrendDocument]:
        """Return cached Telegram trends if not expired."""
        doc = await db.trends.find_one({"platform": self.platform})
        if not doc:
            return None

        expires_at = doc.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) > expires_at:
                logger.info("Cached Telegram trends expired")
                return None

        try:
            return TrendDocument(**doc)
        except Exception as exc:
            logger.error("Failed to parse cached Telegram trends: %s", exc, exc_info=True)
            return None
