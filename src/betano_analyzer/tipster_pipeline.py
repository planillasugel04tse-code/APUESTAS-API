from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tipster_intelligence import AnalyzedPick, StatisticalEvidence, TipsterPick, analyze_pick, safer_market
from .tipster_market import MarketQuote, best_market_quote


@dataclass(frozen=True)
class MarketEnrichment:
    """Real stored-market prices attached to one normalized tipster pick."""

    original: MarketQuote | None
    safer: MarketQuote | None


@dataclass(frozen=True)
class EnrichedTipsterResult:
    """Analysis plus the market evidence used to price the pick."""

    analysis: AnalyzedPick
    market: MarketEnrichment


def enrich_tipster_pick(
    match_id: int,
    pick: TipsterPick,
    evidence: StatisticalEvidence,
    *,
    max_age_minutes: int = 180,
) -> EnrichedTipsterResult:
    """Attach fresh stored odds and analyze a tipster pick.

    This is deliberately storage-only: it does not call bookmakers and cannot
    place bets. The caller can use the returned prices to show where the best
    currently stored market quote exists.
    """
    original = best_market_quote(
        match_id,
        pick.market,
        pick.selection,
        line=pick.line,
        max_age_minutes=max_age_minutes,
    )

    safer_candidate = safer_market(pick)
    safer = None
    if (safer_candidate.safer_market, safer_candidate.safer_selection) != (
        pick.market,
        pick.selection,
    ):
        safer = best_market_quote(
            match_id,
            safer_candidate.safer_market,
            safer_candidate.safer_selection,
            max_age_minutes=max_age_minutes,
        )

    priced_pick = pick
    if original is not None:
        priced_pick = TipsterPick(
            source=pick.source,
            source_type=pick.source_type,
            event=pick.event,
            market=pick.market,
            selection=pick.selection,
            odds=original.odds,
            line=pick.line,
            sport=pick.sport,
            league=pick.league,
            published_at=pick.published_at,
            raw_text=pick.raw_text,
            source_url=pick.source_url,
            confidence=pick.confidence,
        )

    safer_odds = safer.odds if safer is not None else None
    analysis = analyze_pick(priced_pick, evidence, safer_odds=safer_odds)
    return EnrichedTipsterResult(
        analysis=analysis,
        market=MarketEnrichment(original=original, safer=safer),
    )


def serialize_enriched(result: EnrichedTipsterResult) -> dict[str, Any]:
    """Return a UI/API-safe representation without exposing storage internals."""
    analysis = result.analysis
    return {
        "analysis": {
            "status": analysis.status,
            "probability": analysis.probability,
            "fair_odds": analysis.fair_odds,
            "offered_odds": analysis.offered_odds,
            "edge": analysis.edge,
            "value_score": analysis.value_score,
            "safety_score": analysis.safety_score,
            "rejection_reasons": list(analysis.rejection_reasons),
            "pick": {
                "source": analysis.pick.source,
                "source_type": analysis.pick.source_type,
                "event": analysis.pick.event,
                "market": analysis.pick.market,
                "selection": analysis.pick.selection,
                "odds": analysis.pick.odds,
                "line": analysis.pick.line,
                "sport": analysis.pick.sport,
                "league": analysis.pick.league,
            },
            "safer": {
                "market": analysis.safer.safer_market,
                "selection": analysis.safer.safer_selection,
                "odds": analysis.safer.safer_odds,
                "edge": analysis.safer.safer_edge,
                "selected": analysis.safer.selected,
                "reason": analysis.safer.reason,
            },
        },
        "market": {
            "original": _quote_dict(result.market.original),
            "safer": _quote_dict(result.market.safer),
        },
    }


def _quote_dict(quote: MarketQuote | None) -> dict[str, Any] | None:
    if quote is None:
        return None
    return {
        "bookmaker": quote.bookmaker,
        "odds": quote.odds,
        "market": quote.market,
        "selection": quote.selection,
        "line": quote.line,
        "captured_at": quote.captured_at,
        "age_seconds": round(quote.age_seconds, 1),
    }
