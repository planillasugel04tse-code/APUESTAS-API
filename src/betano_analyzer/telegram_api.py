from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .telegram.backtest import evaluate_telegram_backtest
from .telegram.config import load_telegram_config
from .telegram.service import process_telegram_signal, retry_pending_matches

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


class TelegramMessage(BaseModel):
    channel: str
    message_id: str
    text: str
    tipster: str | None = None


@router.post("/signals")
def ingest_telegram_signal(data: TelegramMessage):
    """Process a Telegram tipster message through the full analysis pipeline."""
    try:
        return process_telegram_signal(
            data.text, channel=data.channel, message_id=data.message_id, tipster=data.tipster
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/signals")
def list_telegram_signals(limit: int = 50):
    """Return the most recent processed Telegram signals."""
    limit = max(1, min(limit, 200))
    from .db import connect
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM telegram_signals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return {"count": len(rows), "signals": [dict(row) for row in rows]}


@router.get("/config")
def telegram_config_status():
    """Return safe Telegram configuration status without exposing secrets."""
    config = load_telegram_config()
    return {
        "enabled": config.enabled,
        "configured": config.is_configured,
        "valid": not config.validation_errors,
        "session_name": config.session_name,
        "channels": config.channels if config.channels is not None else "all",
        "has_api_id": config.api_id is not None,
        "has_api_hash": bool(config.api_hash),
        "has_phone": bool(config.phone),
        "validation_errors": config.validation_errors,
    }


@router.post("/retry-pending")
def retry_pending():
    """Re-attempt event matching for all signals still in 'pending_match'."""
    try:
        return retry_pending_matches()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/backtest")
def telegram_backtest(tipster: str | None = None, channel: str | None = None):
    """Backtest settled Telegram picks using the core backtest engine."""
    return evaluate_telegram_backtest(tipster=tipster, channel=channel)
