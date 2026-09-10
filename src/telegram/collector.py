import asyncio
import logging
from typing import Optional, List, Callable

from telethon import TelegramClient, events
from .config import load_telegram_config, TelegramConfig
from .pipeline import process_telegram_message

logger = logging.getLogger("betting_analyzer.telegram")

class TelegramCollector:
    """Asynchronous Telethon client listener for authorized Telegram channels."""

    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or load_telegram_config()
        self.client: Optional[TelegramClient] = None
        self.message_handler: Optional[Callable] = process_telegram_message

    def set_handler(self, handler: Callable):
        """Set custom callback for incoming messages."""
        self.message_handler = handler

    async def start(self, run_forever: bool = True):
        """Start Telegram client session and attach channel event handlers."""
        if not self.config.is_configured:
            logger.warning("Telegram is not configured or disabled.")
            return

        logger.info("Initializing Telegram Telethon client...")
        self.client = TelegramClient(self.config.session_name, self.config.api_id, self.config.api_hash)

        if self.config.phone:
            await self.client.start(phone=self.config.phone)
        else:
            await self.client.start()

        channels = self.config.channels
        logger.info(f"Connected to Telegram as User. Listening to channels: {channels or 'ALL'}")

        @self.client.on(events.NewMessage(chats=channels if channels else None))
        async def on_new_message(event):
            try:
                raw_text = event.raw_text
                if not raw_text:
                    return

                chat = await event.get_chat()
                chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(event.chat_id)
                channel_identifier = f"@{chat.username}" if getattr(chat, 'username', None) else chat_title
                msg_id = str(event.id)

                logger.info(f"Received message from {channel_identifier} (ID: {msg_id})")

                if self.message_handler:
                    if asyncio.iscoroutinefunction(self.message_handler):
                        await self.message_handler(raw_text, channel_identifier, msg_id)
                    else:
                        self.message_handler(raw_text, channel_identifier, msg_id)
            except Exception as e:
                logger.error(f"Error handling Telegram message: {e}", exc_info=True)

        if run_forever:
            await self.client.run_until_disconnected()

    async def stop(self):
        """Disconnect client."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()

def start_telegram_listener():
    """Synchronous entry point to start the live Telegram listener loop."""
    collector = TelegramCollector()
    asyncio.run(collector.start(run_forever=True))
