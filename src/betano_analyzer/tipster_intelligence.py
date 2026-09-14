from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import isfinite
from typing import Any


MIN_ODD = 1.40
TARGET_MAX_ODD = 2.10
HARD_MAX_ODD = 2.50
MAX_LEGS = 3


@dataclass(frozen=True)
class TipsterPick:
    source: str
    source_type: str
    event: str
    market: str
    selection: str
    odds: float | None = None
    line: float | None = None
    sport: str = ""
    league: str = ""
    published_at: str | None = None
    raw_text: str = ""
    source_url: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class StatisticalEvidence:
    sample_size: int = 0
    model_probability: float | None = None
    market_probability: float | None = None
    recent_form_score: float | None = None
    referee_score: float | None = None
    agreement_score: float | None = None
    data_completeness: float = 0.0


@dataclass(frozen=True)
class SaferSelection:
    original_market: str
    original_selection: str
    safer_market: str
    safer_selection: str
    reason: str


@dataclass(frozen=True)
class AnalyzedPick:
    pick: TipsterPick
    safer: SaferSelection
    probability: float
    fair_odds: float
    offered_odds: float | None
    edge: float | None
    value_score: float
    safety_score: float
    evidence: StatisticalEvidence
    status: str


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _prob_from_odds(odds: float | None) -> float | None:
    if odds is None or odds <= 1:
        return None
    return 1.0 / odds


def safer_market(pick: TipsterPick) -> SaferSelection:
    market = pick.market.strip().lower()
    selection = pick.selection.strip()

    if market in {"goals", "total goals", "over/under", "totals"}:
        match = re.search(r"(?:over|más de|mas de)\s*(\d+(?:\.\d+)?)", selection, re.I)
        if match:
            line = float(match.group(1))
            if line > 0:
                new_line = max(0.5, line - 1.0)
                return SaferSelection(pick.market, selection, "goals", f"Over {new_line:g}", "reducción de línea para aumentar cobertura")
        match = re.search(r"(?:under|menos de)\s*(\d+(?:\.\d+)?)", selection, re.I)
        if match:
            line = float(match.group(1))
            new_line = line + 1.0
            return SaferSelection(pick.market, selection, "goals", f"Under {new_line:g}", "ampliación de línea para aumentar cobertura")

    if market in {"1x2", "resultado", "match winner", "winner"}:
        low = selection.lower()
        if low in {"local", "home", "1", "gana local"}:
            return SaferSelection(pick.market, selection, "double chance", "1X", "se agrega el empate al lado local")
        if low in {"visitante", "away", "2", "gana visitante"}:
            return SaferSelection(pick.market, selection, "double chance", "X2", "se agrega el empate al lado visitante")

    if market in {"btts", "ambos marcan"}:
        low = selection.lower()
        if low in {"yes", "si", "sí", "ambos marcan"}:
            return SaferSelection(pick.market, selection, "goals", "Over 1.5", "mercado alternativo más amplio")

    return SaferSelection(pick.market, selection, pick.market, selection, "sin transformación automática segura")


def analyze_pick(pick: TipsterPick, evidence: StatisticalEvidence) -> AnalyzedPick:
    market_probability = evidence.market_probability
    model_probability = evidence.model_probability
    base = model_probability if model_probability is not None else market_probability
    if base is None:
        base = _prob_from_odds(pick.odds) or 0.0

    components = [base]
    if evidence.recent_form_score is not None:
        components.append(_clip(evidence.recent_form_score))
    if evidence.referee_score is not None:
        components.append(_clip(evidence.referee_score))
    if evidence.agreement_score is not None:
        components.append(_clip(evidence.agreement_score))

    # Weighted toward the statistical model; missing data reduces confidence rather than inventing evidence.
    probability = _clip(0.55 * base + 0.15 * (evidence.recent_form_score or base) + 0.10 * (evidence.referee_score or base) + 0.20 * (evidence.agreement_score or base))
    if evidence.data_completeness < 1:
        probability *= 0.75 + 0.25 * evidence.data_completeness

    fair_odds = (1 / probability) if probability > 0 else HARD_MAX_ODD
    implied = _prob_from_odds(pick.odds)
    edge = probability - implied if implied is not None else None
    value_score = _clip((edge or 0.0) * 2.5 + 0.5 * probability)
    safety_score = _clip(0.55 * probability + 0.25 * (evidence.data_completeness) + 0.20 * (evidence.agreement_score or probability))

    safer = safer_market(pick)
    status = "VALUE" if edge is not None and edge >= 0.04 else "WATCH"
    if pick.odds is not None and (pick.odds < MIN_ODD or pick.odds > HARD_MAX_ODD):
        status = "REJECT_ODDS"

    return AnalyzedPick(pick, safer, probability, fair_odds, pick.odds, edge, value_score, safety_score, evidence, status)


def select_best_combinada(candidates: list[AnalyzedPick], max_legs: int = MAX_LEGS) -> list[AnalyzedPick]:
    """Select at most 3 independent-looking legs in the target total-odds band.

    The function never promises a win. It rejects legs outside the hard odds range and
    prefers high safety/value with diversity across events.
    """
    eligible = [
        c for c in candidates
        if c.status == "VALUE"
        and c.offered_odds is not None
        and MIN_ODD <= c.offered_odds <= HARD_MAX_ODD
    ]
    eligible.sort(key=lambda c: (c.safety_score, c.value_score), reverse=True)

    selected: list[AnalyzedPick] = []
    events: set[str] = set()
    for candidate in eligible:
        if candidate.pick.event in events:
            continue
        selected.append(candidate)
        events.add(candidate.pick.event)
        if len(selected) >= max(1, min(MAX_LEGS, max_legs)):
            break

    total = 1.0
    for candidate in selected:
        total *= candidate.offered_odds or 1.0

    # Prefer 2 legs when 3 legs pushes the ticket above the target range.
    if total > HARD_MAX_ODD and len(selected) > 2:
        selected = selected[:2]
    return selected


def serialize(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {k: serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    return value


def parse_basic_tipster_text(text: str, source: str, source_type: str, source_url: str | None = None) -> TipsterPick | None:
    if not text or not text.strip():
        return None
    clean = " ".join(text.split())
    odds_match = re.search(r"(?:cuota|odds|@)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", clean, re.I)
    odds = float(odds_match.group(1).replace(",", ".")) if odds_match else None
    event_match = re.search(r"([\wÀ-ÿ .'-]{2,})\s+(?:vs|v|contra)\s+([\wÀ-ÿ .'-]{2,})", clean, re.I)
    event = f"{event_match.group(1).strip()} vs {event_match.group(2).strip()}" if event_match else clean[:120]
    market = ""
    selection = clean
    if re.search(r"\b(over|más de|mas de|under|menos de)\b", clean, re.I):
        market = "goals"
    elif re.search(r"\b(local|home|visitante|away|1x2)\b", clean, re.I):
        market = "1x2"
    elif re.search(r"\b(btts|ambos marcan)\b", clean, re.I):
        market = "btts"
    else:
        market = "general"
    if odds_match:
        selection = clean[:odds_match.start()].strip(" -:") or clean
    return TipsterPick(source=source, source_type=source_type, event=event, market=market, selection=selection, odds=odds, raw_text=text, source_url=source_url, published_at=datetime.now(timezone.utc).isoformat())
