from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, events

from .config import TelegramConfig, load_telegram_config
from .service import process_telegram_signal

logger = logging.getLogger(__name__)


class TelegramCollector:
    """Live Telegram source adapter; it never contains betting decision logic."""

    def __init__(self, config: TelegramConfig | None = None):
        self.config = config or load_telegram_config()
        self.client: TelegramClient | None = None

    async def start(self, run_forever: bool = True) -> None:
        if not self.config.is_configured:
            logger.warning("Telegram is disabled or not configured")
            return
        self.client = TelegramClient(self.config.session_name, self.config.api_id, self.config.api_hash)
        if self.config.phone:
            await self.client.start(phone=self.config.phone)
        else:
            await self.client.start()

        @self.client.on(events.NewMessage(chats=self.config.channels))
        async def on_message(event):
            if not event.raw_text:
                return
            chat = await event.get_chat()
            channel = getattr(chat, "username", None) or getattr(chat, "title", None) or str(event.chat_id)
            try:
                process_telegram_signal(event.raw_text, channel=str(channel), message_id=str(event.id))
            except Exception:
                logger.exception("Telegram signal processing failed for %s:%s", channel, event.id)

        if run_forever:
            await self.client.run_until_disconnected()

    async def stop(self) -> None:
        if self.client and self.client.is_connected():
            await self.client.disconnect()


def start_telegram_listener() -> None:
    asyncio.run(TelegramCollector().start(run_forever=True))
