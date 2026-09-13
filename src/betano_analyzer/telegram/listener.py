from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, events

from .config import load_telegram_config
from .service import process_telegram_signal

logger = logging.getLogger(__name__)


def _channel_allowed(channels: list[str] | None, event) -> bool:
    if not channels:
        return True
    candidates = set()
    chat = getattr(event, "chat", None)
    username = getattr(chat, "username", None)
    title = getattr(chat, "title", None)
    if username:
        candidates.update({username.lower(), f"@{username.lower()}"})
    if title:
        candidates.add(str(title).strip().lower())
    configured = {str(item).strip().lower() for item in channels}
    return bool(candidates & configured)


def build_client() -> TelegramClient:
    config = load_telegram_config()
    if not config.is_configured:
        errors = ", ".join(config.validation_errors) or "Telegram está deshabilitado"
        raise RuntimeError(errors)
    return TelegramClient(config.session_name, config.api_id, config.api_hash)


async def run_listener() -> None:
    """Listen to configured Telegram channels and feed messages into the analyzer.

    The listener only reads messages and stores them through the existing
    Telegram analysis pipeline. It does not send messages, place bets, or
    modify Telegram content.
    """
    config = load_telegram_config()
    client = build_client()
    channels = config.channels

    @client.on(events.NewMessage(incoming=True))
    async def on_message(event):
        if not _channel_allowed(channels, event):
            return
        text = event.raw_text or ""
        if not text.strip():
            return
        chat = await event.get_chat()
        channel_name = getattr(chat, "username", None) or getattr(chat, "title", None) or str(event.chat_id)
        message_id = str(event.id)
        try:
            result = process_telegram_signal(text, channel=str(channel_name), message_id=message_id)
            logger.info("Telegram signal %s processed: %s", message_id, result.get("status"))
        except Exception:
            logger.exception("Telegram signal %s failed", message_id)

    logger.info("Telegram listener starting; channels=%s", channels or "all")
    await client.start(phone=config.phone or None)
    await client.run_until_disconnected()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_listener())


if __name__ == "__main__":
    main()
