from __future__ import annotations

import os
from dataclasses import dataclass


def _channels(value: str | None) -> list[str] | None:
    if not value or value.strip().lower() in {"*", "all", "todos"}:
        return None
    return [item.strip() for item in value.split(",") if item.strip()] or None


@dataclass(frozen=True)
class TelegramConfig:
    api_id: int | None
    api_hash: str | None
    phone: str | None
    session_name: str
    channels: list[str] | None
    enabled: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_id and self.api_hash)


def load_telegram_config() -> TelegramConfig:
    raw_id = os.getenv("TELEGRAM_API_ID")
    return TelegramConfig(
        api_id=int(raw_id) if raw_id and raw_id.isdigit() else None,
        api_hash=os.getenv("TELEGRAM_API_HASH"),
        phone=os.getenv("TELEGRAM_PHONE"),
        session_name=os.getenv("TELEGRAM_SESSION_NAME", "telebet_session"),
        channels=_channels(os.getenv("TELEGRAM_CHANNELS")),
        enabled=os.getenv("TELEGRAM_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
    )
