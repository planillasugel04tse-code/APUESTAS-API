from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .db import connect, initialize
from .peru_bookmakers import registry_slugs
from .team_statistics import build_match_probability
from .tipster_intelligence import AnalyzedPick, StatisticalEvidence, TipsterPick, analyze_pick, safer_market
from .tipster_market import MarketQuote, best_market_quote, best_market_quotes


@dataclass(frozen=True)
class MarketEnrichment:
    """Real stored-market prices attached to one normalized tipster pick."""
    original: MarketQuote | None
    safer: MarketQuote | None
    peru: tuple[MarketQuote, ...] = ()


@dataclass(frozen=True)
class StatisticalEnrichment:
    """Stored historical evidence used when it is sufficiently complete."""
    status: str
    selection_probability: float | None
    sample_size: int
    data_completeness: float
    home_team: str | None
    away_team: str | None
    source: str
    no_invention: bool = True


@dataclass(frozen=True)
class EnrichedTipsterResult:
    """Analysis plus market and statistical evidence used to price the pick."""
    analysis: AnalyzedPick
    market: MarketEnrichment
    statistics: StatisticalEnrichment


def _as_market_quote(value: MarketQuote | dict[str, object] | None) -> MarketQuote | None:
    """Normalize the legacy dict return of best_market_quote to MarketQuote."""
    if value is None:
        return None
    if isinstance(value, MarketQuote):
        return value
    return MarketQuote(
        bookmaker=str(value["bookmaker"]), odds=float(value["odds"]), market=str(value["market"]),
        selection=str(value["selection"]), line=float(value["line"]) if value.get("line") is not None else None,
        captured_at=str(value["captured_at"]), age_seconds=float(value["age_seconds"]),
    )


def _match_teams(match_id: int) -> tuple[str | None, str | None]:
    initialize()
    with connect() as db:
        row = db.execute("SELECT home_team, away_team FROM matches WHERE id = ?", (match_id,)).fetchone()
    if row is None:
        return None, None
    return str(row["home_team"]), str(row["away_team"])


def _statistical_enrichment(match_id: int, pick: TipsterPick) -> StatisticalEnrichment:
    home_team, away_team = _match_teams(match_id)
    if not home_team or not away_team:
        return StatisticalEnrichment("MATCH_NOT_FOUND", None, 0, 0.0, home_team, away_team, "stored_team_match_history")

    result = build_match_probability(home_team, away_team, pick.market, pick.selection)
    home_report = result["home_report"]
    away_report = result["away_report"]
    sample_size = min(int(home_report["sample_size"]), int(away_report["sample_size"]))
    completeness = min(float(home_report["data_completeness"]), float(away_report["data_completeness"]))
    return StatisticalEnrichment(
        status=str(result["status"]),
        selection_probability=result["selection_probability"],
        sample_size=sample_size,
        data_completeness=round(completeness, 4),
        home_team=home_team,
        away_team=away_team,
        source=str(result["source"]),
    )


def _selection_line(selection: str) -> float | None:
    """Extract a numeric total/handicap line from a transformed selection."""
    match = re.search(r"(?:over|under|más de|mas de|menos de)\s*(-?\d+(?:\.\d+)?)", selection, re.I)
    if match:
        return float(match.group(1))
    return None


def enrich_tipster_pick(
    match_id: int,
    pick: TipsterPick,
    evidence: StatisticalEvidence,
    *,
    max_age_minutes: int = 180,
) -> EnrichedTipsterResult:
    """Attach fresh stored odds and historical statistics without external calls.

    The analyzer compares the full stored market but, when a verified Peru
    quote exists, uses that Peru price as the executable price for value/safety
    analysis. This keeps international prices visible without accidentally
    pricing a Peru workflow from a non-Peru bookmaker.
    """
    original = _as_market_quote(
        best_market_quote(
            match_id,
            pick.market,
            pick.selection,
            line=pick.line,
            max_age_minutes=max_age_minutes,
        )
    )
    peru_quotes = tuple(
        best_market_quotes(
            match_id,
            pick.market,
            pick.selection,
            line=pick.line,
            max_age_minutes=max_age_minutes,
            bookmakers=registry_slugs(),
        )
    )

    safer_candidate = safer_market(pick)
    safer = None
    if (safer_candidate.safer_market, safer_candidate.safer_selection) != (pick.market, pick.selection):
        safer_line = _selection_line(safer_candidate.safer_selection)
        safer = _as_market_quote(
            best_market_quote(
                match_id,
                safer_candidate.safer_market,
                safer_candidate.safer_selection,
                line=safer_line,
                max_age_minutes=max_age_minutes,
            )
        )

    statistics = _statistical_enrichment(match_id, pick)
    analysis_quote = peru_quotes[0] if peru_quotes else original
    priced_pick = pick
    if analysis_quote is not None:
        priced_pick = TipsterPick(
            source=pick.source,
            source_type=pick.source_type,
            event=pick.event,
            market=pick.market,
            selection=pick.selection,
            odds=analysis_quote.odds,
            line=pick.line,
            sport=pick.sport,
            league=pick.league,
            published_at=pick.published_at,
            raw_text=pick.raw_text,
            source_url=pick.source_url,
            confidence=pick.confidence,
        )

    enriched_evidence = evidence
    if statistics.selection_probability is not None and statistics.status == "OK":
        enriched_evidence = StatisticalEvidence(
            sample_size=max(evidence.sample_size, statistics.sample_size),
            model_probability=evidence.model_probability if evidence.model_probability is not None else statistics.selection_probability,
            market_probability=evidence.market_probability,
            recent_form_score=evidence.recent_form_score,
            referee_score=evidence.referee_score,
            agreement_score=evidence.agreement_score,
            data_completeness=max(evidence.data_completeness, statistics.data_completeness),
        )
    safer_odds = safer.odds if safer is not None else None
    analysis = analyze_pick(priced_pick, enriched_evidence, safer_odds=safer_odds)
    return EnrichedTipsterResult(
        analysis=analysis,
        market=MarketEnrichment(original=original, safer=safer, peru=peru_quotes),
        statistics=statistics,
    )


def serialize_enriched(result: EnrichedTipsterResult) -> dict[str, Any]:
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
            "price_source": (
                result.market.peru[0].bookmaker if result.market.peru else (result.market.original.bookmaker if result.market.original else None)
            ),
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
            "peru": [_quote_dict(quote) for quote in result.market.peru],
            "peru_best": _quote_dict(result.market.peru[0]) if result.market.peru else None,
        },
        "statistics": asdict(result.statistics),
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
