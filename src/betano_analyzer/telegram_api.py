from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .telegram.service import process_telegram_signal

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


class TelegramMessage(BaseModel):
    channel: str
    message_id: str
    text: str
    tipster: str | None = None


@router.post("/signals")
def ingest_telegram_signal(data: TelegramMessage):
    try:
        return process_telegram_signal(
            data.text,
            channel=data.channel,
            message_id=data.message_id,
            tipster=data.tipster,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/signals")
def list_telegram_signals(limit: int = 50):
    limit = max(1, min(limit, 200))
    from .db import connect
    with connect() as db:
        rows = db.execute("SELECT * FROM telegram_signals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return {"count": len(rows), "signals": [dict(row) for row in rows]}
