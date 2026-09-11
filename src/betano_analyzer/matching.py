from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class MatchCandidate:
    match_id: int
    score: float


# ---------------------------------------------------------------------------
# Phrase-level aliases applied BEFORE token splitting.
# These must be specific enough not to cause collisions with other team names.
# ---------------------------------------------------------------------------
_TEAM_PHRASE_ALIASES: tuple[tuple[str, str], ...] = (
    # Manchester United variants
    (r"\bmanchester\s+utd\b", "manchester united"),
    (r"\bman\s+utd\b", "manchester united"),
    (r"\bman\s+united\b", "manchester united"),
    # Barcelona variants
    (r"\bfc\s+barcelona\b", "barcelona"),
    (r"\bbarca\b", "barcelona"),
    (r"\bbarcelona\b", "barcelona"),
    # Paris Saint-Germain variants
    (r"\bpsg\b", "paris saint germain"),
    (r"\bparis\s+sg\b", "paris saint germain"),
    (r"\bparis\s+saint.germain\b", "paris saint germain"),
    # Bayern Munich variants
    (r"\bbayern\s+munchen\b", "bayern munich"),
    (r"\bfc\s+bayern\b", "bayern munich"),
    (r"\bbayern\s+munich\b", "bayern munich"),
    # Juventus variants
    (r"\bjuventus\b", "juventus"),
    (r"\bjuve\b", "juventus"),
    # Inter Milan variants
    (r"\binter\s+milan\b", "inter milan"),
    (r"\bfc\s+inter\b", "inter milan"),
    # AC Milan
    (r"\bac\s+milan\b", "ac milan"),
    # Real Madrid
    (r"\breal\s+madrid\b", "real madrid"),
    # Atletico de Madrid variants
    (r"\batletico\s+madrid\b", "atletico de madrid"),
    (r"\batl[eé]tico\s+de\s+madrid\b", "atletico de madrid"),
    (r"\batl\.\s*madrid\b", "atletico de madrid"),
    # Borussia Dortmund variants
    (r"\bbvb\b", "borussia dortmund"),
    # RB Leipzig
    (r"\brb\s+leipzig\b", "rb leipzig"),
    (r"\blipsia\b", "rb leipzig"),
    # Bayer Leverkusen
    (r"\bleverkusen\b", "bayer leverkusen"),
    # Tottenham variants
    (r"\bspurs\b", "tottenham"),
    (r"\btottenham\s+hotspur\b", "tottenham"),
    # Arsenal
    (r"\barsenal\s+fc\b", "arsenal"),
    # Chelsea
    (r"\bchelsea\s+fc\b", "chelsea"),
    # Liverpool
    (r"\bliverpool\s+fc\b", "liverpool"),
    # Manchester City
    (r"\bman\s+city\b", "manchester city"),
    # Benfica
    (r"\bsl\s+benfica\b", "benfica"),
    (r"\bbenfica\b", "benfica"),
    # Porto
    (r"\bfc\s+porto\b", "porto"),
    # Sporting CP variants
    (r"\bsporting\s+cp\b", "sporting"),
    (r"\bsporting\s+lisboa\b", "sporting"),
    # Ajax
    (r"\bajax\s+amsterdam\b", "ajax"),
    # AS Roma
    (r"\broma\b", "roma"),
    (r"\bas\s+roma\b", "roma"),
    # Lazio
    (r"\bss\s+lazio\b", "lazio"),
    # Napoli
    (r"\bssc\s+napoli\b", "napoli"),
    # Sevilla
    (r"\bsevilla\s+fc\b", "sevilla"),
    # Valencia
    (r"\bvalencia\s+cf\b", "valencia"),
    # Villarreal
    (r"\bvillarreal\s+cf\b", "villarreal"),
    # Alianza Lima (Perú)
    (r"\balianza\s+lima\b", "alianza lima"),
    # Universitario (Perú)
    (r"\buniversitario\s+de\s+deportes\b", "universitario"),
    (r"\bla\s+u\b", "universitario"),
    # Sporting Cristal (Perú)
    (r"\bsporting\s+cristal\b", "sporting cristal"),
    # Flamengo (Brasil)
    (r"\bcr\s+flamengo\b", "flamengo"),
    # River Plate / Boca Juniors (Argentina)
    (r"\briver\s+plate\b", "river plate"),
    (r"\bboca\s+juniors\b", "boca juniors"),
)

# ---------------------------------------------------------------------------
# Token-level aliases applied AFTER phrase aliases and lowercasing.
# Tokens that match a key are replaced by the value (empty string = remove).
# ---------------------------------------------------------------------------
_TOKEN_ALIASES: dict[str, str] = {
    "utd": "united",
    "united": "united",
    "fc": "",
    "cf": "",
    "sc": "",
    "afc": "",
    "bfc": "",
    "fk": "",
    "sk": "",
    "hk": "",
    "club": "",
    "real": "real",
    "atletico": "atletico",
    "deportivo": "deportivo",
    "sporting": "sporting",
    "sport": "sport",
}


def normalize_team_name(value: str) -> str:
    """Return a canonical, accent-free, lower-case team key for matching.

    1. Unicode NFKD decomposition removes combining accents.
    2. Phrase-level aliases handle multi-word abbreviations safely.
    3. Token aliases strip generic suffixes (FC, CF, SC ...).
    """
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    for pattern, replacement in _TEAM_PHRASE_ALIASES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    tokens: list[str] = []
    for token in text.split():
        mapped = _TOKEN_ALIASES.get(token, token)
        if mapped:
            tokens.append(mapped)
    return " ".join(tokens)


def _similar(left: str, right: str) -> float:
    """Return a similarity score between two normalized team name strings."""
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.94
    return SequenceMatcher(None, left, right).ratio()


def rank_team_match(home: str, away: str, candidates: list[dict]) -> list[MatchCandidate]:
    """Rank DB match candidates by name similarity; caller decides acceptance threshold."""
    home_key = normalize_team_name(home)
    away_key = normalize_team_name(away)
    ranked: list[MatchCandidate] = []
    for row in candidates:
        score_home = _similar(home_key, normalize_team_name(str(row["home_team"])))
        score_away = _similar(away_key, normalize_team_name(str(row["away_team"])))
        ranked.append(MatchCandidate(int(row["id"]), round((score_home + score_away) / 2, 6)))
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def choose_team_match(
    home: str,
    away: str,
    candidates: list[dict],
    *,
    minimum_score: float = 0.90,
    minimum_gap: float = 0.05,
) -> MatchCandidate | None:
    """Return the unambiguous best match, or None if the signal is too weak.

    The function is intentionally conservative:
    - Score must exceed ``minimum_score`` (default 0.90).
    - The gap between the top-2 scores must exceed ``minimum_gap`` (default 0.05)
      to prevent associating a signal with the wrong fixture when two similar
      teams appear in the candidate list simultaneously.
    """
    ranked = rank_team_match(home, away, candidates)
    if not ranked or ranked[0].score < minimum_score:
        return None
    if len(ranked) > 1 and ranked[0].score - ranked[1].score < minimum_gap:
        return None
    return ranked[0]
