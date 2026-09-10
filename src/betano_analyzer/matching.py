from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class MatchCandidate:
    match_id: int
    score: float


# Conservative aliases for common football abbreviations. These are phrase-level
# aliases where a generic token such as "man" would be unsafe on its own.
_TEAM_PHRASE_ALIASES = (
    (r"\bmanchester\s+utd\b", "manchester united"),
    (r"\bman\s+utd\b", "manchester united"),
    (r"\bman\s+united\b", "manchester united"),
    (r"\bmanchester\s+united\b", "manchester united"),
)


def normalize_team_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    for pattern, replacement in _TEAM_PHRASE_ALIASES:
        text = re.sub(pattern, replacement, text)
    tokens = []
    aliases = {
        "utd": "united",
        "united": "united",
        "fc": "",
        "cf": "",
        "sc": "",
        "afc": "",
        "club": "",
        "deportivo": "deportivo",
    }
    for token in text.split():
        mapped = aliases.get(token, token)
        if mapped:
            tokens.append(mapped)
    return " ".join(tokens)


def _similar(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.94
    return SequenceMatcher(None, left, right).ratio()


def rank_team_match(home: str, away: str, candidates: list[dict]) -> list[MatchCandidate]:
    """Rank candidates conservatively; caller decides whether the top score is safe."""
    home_key = normalize_team_name(home)
    away_key = normalize_team_name(away)
    ranked: list[MatchCandidate] = []
    for row in candidates:
        score_home = _similar(home_key, normalize_team_name(str(row["home_team"])))
        score_away = _similar(away_key, normalize_team_name(str(row["away_team"])))
        ranked.append(MatchCandidate(int(row["id"]), round((score_home + score_away) / 2, 6)))
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def choose_team_match(home: str, away: str, candidates: list[dict], *, minimum_score: float = 0.90, minimum_gap: float = 0.05) -> MatchCandidate | None:
    ranked = rank_team_match(home, away, candidates)
    if not ranked or ranked[0].score < minimum_score:
        return None
    if len(ranked) > 1 and ranked[0].score - ranked[1].score < minimum_gap:
        return None
    return ranked[0]
