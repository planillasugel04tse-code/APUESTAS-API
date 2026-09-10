import os
from dataclasses import dataclass

def _parse_channels(env_val: str | None) -> list[str] | None:
    if not env_val or env_val.strip().lower() in {"*", "all", "todos", ""}:
        return None
    channels = [c.strip() for c in env_val.split(",") if c.strip()]
    return channels if channels else None

def mask_secret(value: str | int | None) -> str:
    """Mask secret credentials for logging."""
    if not value:
        return "<not-configured>"
    s = str(value).strip()
    if len(s) <= 4:
        return "****"
    return s[:2] + "*" * (len(s) - 4) + s[-2:]

@dataclass(frozen=True)
class TelegramConfig:
    api_id: int | None
    api_hash: str | None
    bot_token: str | None
    phone: str | None
    session_name: str
    channels: list[str] | None
    enabled: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and ((self.api_id and self.api_hash) or self.bot_token))

def load_telegram_config() -> TelegramConfig:
    api_id_raw = os.getenv("TELEGRAM_API_ID")
    api_id = int(api_id_raw) if api_id_raw and api_id_raw.strip().isdigit() else None
    return TelegramConfig(
        api_id=api_id,
        api_hash=os.getenv("TELEGRAM_API_HASH"),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        phone=os.getenv("TELEGRAM_PHONE"),
        session_name=os.getenv("TELEGRAM_SESSION_NAME", "telebet_session"),
        channels=_parse_channels(os.getenv("TELEGRAM_CHANNELS")),
        enabled=os.getenv("TELEGRAM_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
    )
