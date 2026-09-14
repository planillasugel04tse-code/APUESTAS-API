from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import combinations
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
    safer_odds: float | None = None
    safer_edge: float | None = None
    selected: bool = False


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
    rejection_reasons: tuple[str, ...] = ()


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _prob_from_odds(odds: float | None) -> float | None:
    if odds is None or odds <= 1:
        return None
    return 1.0 / odds


def safer_market(pick: TipsterPick, safer_odds: float | None = None) -> SaferSelection:
    market = pick.market.strip().lower()
    selection = pick.selection.strip()

    if market in {"goals", "total goals", "over/under", "totals"}:
        match = re.search(r"(?:over|más de|mas de)\s*(\d+(?:\.\d+)?)", selection, re.I)
        if match:
            line = float(match.group(1))
            new_line = max(0.5, line - 1.0)
            return SaferSelection(pick.market, selection, "goals", f"Over {new_line:g}", "reducción de línea para aumentar cobertura", safer_odds)
        match = re.search(r"(?:under|menos de)\s*(\d+(?:\.\d+)?)", selection, re.I)
        if match:
            line = float(match.group(1))
            return SaferSelection(pick.market, selection, "goals", f"Under {line + 1:g}", "ampliación de línea para aumentar cobertura", safer_odds)

    if market in {"1x2", "resultado", "match winner", "winner"}:
        low = selection.lower()
        if low in {"local", "home", "1", "gana local"}:
            return SaferSelection(pick.market, selection, "double chance", "1X", "se agrega el empate al lado local", safer_odds)
        if low in {"visitante", "away", "2", "gana visitante"}:
            return SaferSelection(pick.market, selection, "double chance", "X2", "se agrega el empate al lado visitante", safer_odds)

    if market in {"btts", "ambos marcan"} and selection.lower() in {"yes", "si", "sí", "ambos marcan"}:
        return SaferSelection(pick.market, selection, "goals", "Over 1.5", "mercado alternativo más amplio", safer_odds)

    return SaferSelection(pick.market, selection, pick.market, selection, "sin transformación automática segura", safer_odds)


def _combined_probability(evidence: StatisticalEvidence, pick: TipsterPick) -> float:
    market_probability = evidence.market_probability
    model_probability = evidence.model_probability
    base = model_probability if model_probability is not None else market_probability
    if base is None:
        base = _prob_from_odds(pick.odds) or 0.0

    # Missing dimensions never count as positive evidence. They only reduce confidence.
    probability = (
        0.55 * base
        + 0.15 * (evidence.recent_form_score if evidence.recent_form_score is not None else base)
        + 0.10 * (evidence.referee_score if evidence.referee_score is not None else base)
        + 0.20 * (evidence.agreement_score if evidence.agreement_score is not None else base)
    )
    completeness = _clip(evidence.data_completeness)
    return _clip(probability * (0.75 + 0.25 * completeness))


def analyze_pick(pick: TipsterPick, evidence: StatisticalEvidence, *, safer_odds: float | None = None) -> AnalyzedPick:
    probability = _combined_probability(evidence, pick)
    fair_odds = (1 / probability) if probability > 0 else HARD_MAX_ODD
    implied = _prob_from_odds(pick.odds)
    edge = probability - implied if implied is not None else None
    value_score = _clip((edge or 0.0) * 2.5 + 0.5 * probability)
    safety_score = _clip(
        0.55 * probability
        + 0.25 * _clip(evidence.data_completeness)
        + 0.20 * (evidence.agreement_score if evidence.agreement_score is not None else probability)
    )

    safer = safer_market(pick, safer_odds)
    reasons: list[str] = []
    if pick.odds is not None and pick.odds < MIN_ODD:
        reasons.append(f"cuota inferior a {MIN_ODD:.2f}")
    if pick.odds is not None and pick.odds > HARD_MAX_ODD:
        reasons.append(f"cuota superior al máximo {HARD_MAX_ODD:.2f}")
    if edge is not None and edge < 0.04:
        reasons.append("valor insuficiente: edge menor a 4 puntos porcentuales")
    if evidence.data_completeness < 0.50:
        reasons.append("evidencia estadística incompleta")

    status = "VALUE" if not reasons and edge is not None else "WATCH"
    if pick.odds is not None and (pick.odds < MIN_ODD or pick.odds > HARD_MAX_ODD):
        status = "REJECT_ODDS"
    if edge is not None and edge < 0.04:
        status = "NO_VALUE"

    return AnalyzedPick(
        pick=pick,
        safer=safer,
        probability=probability,
        fair_odds=fair_odds,
        offered_odds=pick.odds,
        edge=edge,
        value_score=value_score,
        safety_score=safety_score,
        evidence=evidence,
        status=status,
        rejection_reasons=tuple(reasons),
    )


def _combo_score(items: tuple[AnalyzedPick, ...]) -> float:
    # Penalize long tickets. The objective is not maximum odds; it is value + safety.
    return sum(item.value_score * 0.55 + item.safety_score * 0.45 for item in items) - 0.05 * (len(items) - 2)


def select_best_combinada(candidates: list[AnalyzedPick], max_legs: int = MAX_LEGS) -> list[AnalyzedPick]:
    """Return the strongest 2-leg ticket, or 3 legs only when it remains in range.

    No ticket is represented as guaranteed. Legs from the same event are excluded to
    avoid obvious correlation and only VALUE candidates in the hard odds range qualify.
    """
    max_legs = max(2, min(MAX_LEGS, max_legs))
    eligible = [
        c for c in candidates
        if c.status == "VALUE" and c.offered_odds is not None and MIN_ODD <= c.offered_odds <= HARD_MAX_ODD
    ]

    best: tuple[float, tuple[AnalyzedPick, ...]] | None = None
    for size in (2, 3):
        if size > max_legs:
            continue
        for combo in combinations(eligible, size):
            events = [item.pick.event.strip().lower() for item in combo]
            if len(set(events)) != len(events):
                continue
            total = 1.0
            for item in combo:
                total *= item.offered_odds or 1.0
            if not (MIN_ODD <= total <= HARD_MAX_ODD):
                continue
            score = _combo_score(combo)
            # Prefer two legs when scores are close; three legs need to add meaningful value.
            if size == 2:
                score += 0.04
            if best is None or score > best[0]:
                best = (score, combo)

    return list(best[1]) if best else []


def serialize(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {k: serialize(v) for k, v in asdict(value).items()}
    if isinstance(value, tuple):
        return [serialize(v) for v in value]
    if isinstance(value, list):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    return value


def parse_basic_tipster_text(text: str, source: str, source_type: str, source_url: str | None = None) -> TipsterPick | None:
    if not text or not text.strip():
        return None
    clean = " ".join(text.split())
    odds_match = re.search(r"(?:cuota|odds|momio|@)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", clean, re.I)
    odds = float(odds_match.group(1).replace(",", ".")) if odds_match else None
    event_match = re.search(r"([\wÀ-ÿ .'-]{2,})\s+(?:vs|v|contra)\s+([\wÀ-ÿ .'-]{2,})", clean, re.I)
    event = f"{event_match.group(1).strip()} vs {event_match.group(2).strip()}" if event_match else clean[:120]
    if re.search(r"\b(over|más de|mas de|under|menos de|goles)\b", clean, re.I):
        market = "goals"
    elif re.search(r"\b(local|home|visitante|away|empate|draw|1x2)\b", clean, re.I):
        market = "1x2"
    elif re.search(r"\b(btts|ambos marcan)\b", clean, re.I):
        market = "btts"
    elif re.search(r"\b(corner|córner|corners)\b", clean, re.I):
        market = "corners"
    elif re.search(r"\b(tarjeta|tarjetas|cards)\b", clean, re.I):
        market = "cards"
    else:
        market = "general"
    selection = clean[:odds_match.start()].strip(" -:") if odds_match else clean
    return TipsterPick(
        source=source,
        source_type=source_type,
        event=event,
        market=market,
        selection=selection,
        odds=odds,
        raw_text=text,
        source_url=source_url,
        published_at=datetime.now(timezone.utc).isoformat(),
    )
