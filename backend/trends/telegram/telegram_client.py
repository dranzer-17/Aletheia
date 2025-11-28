"""
Telegram client utilities for fetching channel posts.
"""

from __future__ import annotations

import os
from typing import List

from telethon import TelegramClient
from telethon.errors import RPCError

from config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION_PATH,
    TELEGRAM_CHANNELS,
)
from trends.logger import get_logger

logger = get_logger(__name__)


DEFAULT_TELEGRAM_CHANNELS = [
    "reutersworldchannel",
    "newzindian",
    "Daily_Caller",
    "WorldNews",
    "realDailyWire",
    "NTDNews",
]


def parse_channel_list(value: str | None) -> List[str]:
    """Parse a comma-separated channel list from env."""
    if not value:
        return DEFAULT_TELEGRAM_CHANNELS
    channels = [item.strip().lstrip("@") for item in value.split(",")]
    return [channel for channel in channels if channel]


class TelegramClientManager:
    """Async context manager that yields an authorized Telegram client."""

    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        session_path: str | None = None,
    ) -> None:
        if not api_id or not api_hash:
            raise RuntimeError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in environment/.env"
            )
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path or os.path.join(os.getcwd(), "telegram.session")
        self._client: TelegramClient | None = None

    async def __aenter__(self) -> TelegramClient:
        client = TelegramClient(self.session_path, self.api_id, self.api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "Telegram session not authorized. Run the login script to create the session file."
                )
            self._client = client
            logger.info("Connected to Telegram using session %s", self.session_path)
            return client
        except RPCError as exc:
            await client.disconnect()
            raise RuntimeError(f"Failed to connect to Telegram: {exc}") from exc

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        if self._client:
            await self._client.disconnect()
            logger.info("Disconnected Telegram client")
            self._client = None


def get_configured_channel_list() -> List[str]:
    """Return the configured Telegram channels."""
    return parse_channel_list(TELEGRAM_CHANNELS)


def build_channel_priority_map(channels: List[str]) -> dict[str, int]:
    """Return a mapping of channel handle -> priority index (lower = higher priority)."""
    return {channel.lower(): idx for idx, channel in enumerate(channels)}

