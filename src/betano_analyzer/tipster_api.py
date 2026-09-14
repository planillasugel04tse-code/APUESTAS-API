from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .tipster_intelligence import (
    AnalyzedPick,
    StatisticalEvidence,
    TipsterPick,
    analyze_pick,
    parse_basic_tipster_text,
    select_best_combinada,
    serialize,
)
from .tipster_sources import collect_public_tipsters

router = APIRouter(prefix="/api/v1/tipsters", tags=["tipsters"])
BETMAINS_DIR = Path("data/betmains_uploads")


class TipsterAnalyzeRequest(BaseModel):
    source: str = "manual"
    source_type: str = "tipster"
    event: str
    market: str
    selection: str
    odds: float | None = Field(default=None, gt=1)
    line: float | None = None
    sport: str = ""
    league: str = ""
    model_probability: float | None = Field(default=None, ge=0, le=1)
    recent_form_score: float | None = Field(default=None, ge=0, le=1)
    referee_score: float | None = Field(default=None, ge=0, le=1)
    agreement_score: float | None = Field(default=None, ge=0, le=1)
    data_completeness: float = Field(default=0, ge=0, le=1)
    sample_size: int = Field(default=0, ge=0)


class TextPredictionRequest(BaseModel):
    source: str
    source_type: str = "ai"
    text: str


def _analysis(payload: TipsterAnalyzeRequest) -> AnalyzedPick:
    pick = TipsterPick(
        source=payload.source,
        source_type=payload.source_type,
        event=payload.event,
        market=payload.market,
        selection=payload.selection,
        odds=payload.odds,
        line=payload.line,
        sport=payload.sport,
        league=payload.league,
    )
    evidence = StatisticalEvidence(
        sample_size=payload.sample_size,
        model_probability=payload.model_probability,
        recent_form_score=payload.recent_form_score,
        referee_score=payload.referee_score,
        agreement_score=payload.agreement_score,
        data_completeness=payload.data_completeness,
    )
    return analyze_pick(pick, evidence)


@router.post("/analyze")
def analyze(payload: TipsterAnalyzeRequest) -> dict[str, Any]:
    return serialize(_analysis(payload))


@router.post("/ai")
def analyze_ai_prediction(payload: TextPredictionRequest) -> dict[str, Any]:
    pick = parse_basic_tipster_text(payload.text, payload.source, payload.source_type)
    if not pick:
        raise HTTPException(status_code=400, detail="No se pudo interpretar el pronóstico de IA")
    result = analyze_pick(pick, StatisticalEvidence(data_completeness=0.0))
    return serialize(result)


@router.post("/collect-web")
async def collect_web() -> dict[str, Any]:
    result = await collect_public_tipsters()
    result["picks"] = [serialize(p) for p in result["picks"]]
    return result


@router.post("/combinada")
def best_combinada(payload: list[TipsterAnalyzeRequest]) -> dict[str, Any]:
    analyzed = [_analysis(item) for item in payload]
    selected = select_best_combinada(analyzed, max_legs=3)
    total_odds = 1.0
    for item in selected:
        total_odds *= item.offered_odds or 1.0
    return {
        "rules": {"max_legs": 3, "preferred_odds": [1.40, 2.10], "hard_max_odds": 2.50},
        "selected": [serialize(item) for item in selected],
        "total_odds": round(total_odds, 3),
        "status": "OK" if 1.40 <= total_odds <= 2.50 else "NO_RECOMMENDATION",
    }


@router.post("/betmains/photo")
async def betmains_photo(
    image: UploadFile = File(...),
    note: str = Form(default=""),
) -> dict[str, Any]:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    data = await image.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La imagen supera 10 MB")
    BETMAINS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(image.filename or "jugada.jpg").name.replace(" ", "_")
    destination = BETMAINS_DIR / safe_name
    destination.write_bytes(data)
    return {
        "status": "RECEIVED",
        "source": "Betmains",
        "filename": safe_name,
        "bytes": len(data),
        "note": note,
        "next_step": "La jugada queda en cola de extracción; si el OCR no reconoce el texto, el formulario permite registrar la jugada manualmente.",
    }
