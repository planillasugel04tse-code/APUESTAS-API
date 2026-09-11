from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .telegram.backtest import evaluate_telegram_backtest
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


@router.post("/retry-pending")
def retry_pending():
    """Re-attempt event matching for all signals still in 'pending_match' status.

    Call this after a sync to resolve signals that arrived before the fixture
    existed in the local database.
    """
    try:
        return retry_pending_matches()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/backtest")
def telegram_backtest(tipster: str | None = None, channel: str | None = None):
    """Backtest settled Telegram picks using the core backtest engine."""
    return evaluate_telegram_backtest(tipster=tipster, channel=channel)
