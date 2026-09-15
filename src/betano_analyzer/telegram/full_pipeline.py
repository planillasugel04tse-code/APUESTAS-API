from __future__ import annotations

import json

from ..db import connect
from ..tipster_intelligence import StatisticalEvidence, TipsterPick
from ..tipster_pipeline import enrich_tipster_pick, serialize_enriched
from .parser import parse_telegram_message
from .service import process_telegram_signal


def process_telegram_signal_full(
    raw_text: str,
    *,
    channel: str,
    message_id: str,
    tipster: str | None = None,
    max_age_minutes: int = 180,
) -> dict:
    """Run Telegram ingestion and then the canonical tipster enrichment pipeline.

    The existing Telegram adapter remains responsible for parsing, matching,
    persistence, and the legacy radar outputs. Once a signal is matched, this
    wrapper feeds the same normalized pick into ``tipster_pipeline`` so the
    real stored market quote and persistent statistics are evaluated by the
    canonical value/safety engine.
    """
    result = process_telegram_signal(
        raw_text, channel=channel, message_id=message_id, tipster=tipster
    )
    if result.get("status") != "success":
        return result

    match_id = result.get("match_id")
    if match_id is None:
        return result

    parsed = parse_telegram_message(raw_text, channel=channel, tipster=tipster)
    if not parsed.is_valid:
        return result

    pick = TipsterPick(
        source=parsed.tipster or tipster or channel,
        source_type="telegram",
        event=f"{parsed.home_team} vs {parsed.away_team}",
        market=parsed.market,
        selection=parsed.selection,
        odds=parsed.odds,
        line=parsed.line,
        sport=parsed.sport,
        league=parsed.competition,
        published_at=parsed.published_at,
        raw_text=raw_text,
        confidence=parsed.confidence,
    )
    evidence = StatisticalEvidence()
    enriched = enrich_tipster_pick(
        int(match_id), pick, evidence, max_age_minutes=max_age_minutes
    )
    serialized = serialize_enriched(enriched)

    with connect() as db:
        row = db.execute(
            "SELECT analysis_result FROM telegram_signals WHERE signal_id=?",
            (result.get("signal_id"),),
        ).fetchone()
        existing_analysis: dict = {}
        if row and row["analysis_result"]:
            try:
                existing_analysis = json.loads(row["analysis_result"])
            except (TypeError, json.JSONDecodeError):
                existing_analysis = {}
        existing_analysis["tipster_pipeline"] = serialized
        db.execute(
            "UPDATE telegram_signals SET analysis_result=? WHERE signal_id=?",
            (json.dumps(existing_analysis, ensure_ascii=False), result.get("signal_id")),
        )
        db.commit()

    result = dict(result)
    analysis = dict(result.get("analysis") or {})
    analysis["tipster_pipeline"] = serialized
    result["analysis"] = analysis
    return result
