from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


SUPPORTED_COMPETITIONS = {
    "premier league",
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "champions league",
    "europa league",
    "liga 1 peru",
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


def normalize_competition(value: str) -> str:
    text = " ".join(value.strip().lower().split())
    aliases = {
        "epl": "premier league",
        "english premier league": "premier league",
        "laliga": "la liga",
        "la liga santander": "la liga",
        "serie a italy": "serie a",
        "uefa champions league": "champions league",
        "uefa europa league": "europa league",
        "peruvian liga 1": "liga 1 peru",
        "liga 1": "liga 1 peru",
    }
    return aliases.get(text, text)


def filter_competitions(matches: Iterable[NormalizedMatch]) -> list[NormalizedMatch]:
    return [m for m in matches if normalize_competition(m.competition) in SUPPORTED_COMPETITIONS]


def normalize_market(market: str, selection: str) -> tuple[str, str]:
    m = " ".join(market.strip().lower().split())
    s = " ".join(selection.strip().lower().split())
    aliases = {
        "match winner": "1x2",
        "moneyline": "1x2",
        "double chance": "double_chance",
        "total goals": "goals",
        "over/under": "goals",
        "total corners": "corners",
        "both teams to score": "btts",
    }
    return aliases.get(m, m), s
