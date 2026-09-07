from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


SUPPORTED_COMPETITIONS = {
    "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
    "champions league", "europa league", "liga 1 peru",
}


@dataclass(frozen=True)
class NormalizedMatch:
    external_id: str
    competition: str
    home_team: str
    away_team: str
    kickoff: str


@dataclass(frozen=True)
class NormalizedOdd:
    external_id: str
    bookmaker: str
    market: str
    selection: str
    odds: float
    captured_at: str
    line: float | None = None


def normalize_competition(value: str) -> str:
    text = " ".join(value.strip().lower().split())
    aliases = {
        "epl": "premier league", "english premier league": "premier league",
        "laliga": "la liga", "la liga santander": "la liga",
        "serie a italy": "serie a", "uefa champions league": "champions league",
        "uefa europa league": "europa league", "peruvian liga 1": "liga 1 peru",
        "liga 1": "liga 1 peru",
    }
    return aliases.get(text, text)


def filter_competitions(matches: Iterable[NormalizedMatch]) -> list[NormalizedMatch]:
    return [m for m in matches if normalize_competition(m.competition) in SUPPORTED_COMPETITIONS]


def _period_key(period: str, market: str) -> str:
    text = f"{period} {market}".lower()
    if any(token in text for token in ("1st half", "first half", "1h", "half time", "halftime")):
        return "1h"
    if any(token in text for token in ("2nd half", "second half", "2h")):
        return "2h"
    return "ft"


def normalize_market(market: str, selection: str, period: str = "") -> tuple[str, str]:
    """Map provider market labels to stable internal keys.

    The period is part of the canonical market so full-time prices can never be
    compared with first/second-half prices by accident.
    """
    m = " ".join(str(market).strip().lower().split())
    s = " ".join(str(selection).strip().lower().split())
    combined = f"{m} {s}"
    period_key = _period_key(period, m)

    if any(token in m for token in ("match winner", "full time result", "moneyline", "1x2", "3 way", "3-way")):
        canonical = "1x2"
    elif "double chance" in m:
        canonical = "double_chance"
    elif any(token in m for token in ("asian handicap", "handicap", "spread")):
        canonical = "asian_handicap"
    elif any(token in m for token in ("total goals", "goals over", "over under", "over/under", "totals")):
        canonical = "goals"
    elif "both teams to score" in m or "btts" in m:
        canonical = "btts"
    elif any(token in m for token in ("total corners", "corners over", "corner over", "corner total")):
        canonical = "corners"
    elif any(token in m for token in ("total cards", "cards over", "card total")):
        canonical = "cards"
    else:
        canonical = m.replace(" ", "_")

    if canonical in {"1x2", "double_chance"}:
        selection_aliases = {
            "1": "home", "home": "home", "home win": "home",
            "x": "draw", "draw": "draw", "tie": "draw",
            "2": "away", "away": "away", "away win": "away",
            "1x": "home_or_draw", "x1": "home_or_draw",
            "x2": "draw_or_away", "2x": "draw_or_away",
            "12": "home_or_away", "1 2": "home_or_away",
        }
        s = selection_aliases.get(s, s)
    elif canonical in {"goals", "corners", "cards", "btts"}:
        if s in {"o", "over", "yes"}:
            s = "over" if canonical != "btts" else "yes"
        elif s in {"u", "under", "no"}:
            s = "under" if canonical != "btts" else "no"

    # Keep unknown provider markets isolated rather than pretending they are a
    # supported canonical market. The combined key also prevents period mixing.
    return f"{canonical}_{period_key}", s
