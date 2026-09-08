from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from .ingest import NormalizedOdd, NormalizedMatch, normalize_market
from .providers import fetch_json

ODDSPAPI_BETANO_PE = "betano.pe"
SOCCER_SPORT_ID = 10

TARGET_TOURNAMENT_SLUGS = {
    "premier-league": "Premier League",
    "laliga": "LaLiga",
    "serie-a": "Serie A",
    "bundesliga": "Bundesliga",
    "ligue-1": "Ligue 1",
    "champions-league": "UEFA Champions League",
    "europa-league": "UEFA Europa League",
    "liga-1": "Liga 1 Peru",
}

_MARKET_CATALOG_CACHE: list[dict[str, Any]] | None = None
_MARKET_CATALOG_CACHE_AT: datetime | None = None
_MARKET_CATALOG_TTL_SECONDS = 300


def _iso(value: Any) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _line_from_text(text: str) -> float | None:
    import re
    matches = re.findall(r"(?:^|[^\d])(-?\d+(?:\.\d+)?)(?:[^\d]|$)", text or "")
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def _line_from_outcome_id(value: Any) -> float | None:
    if value is None:
        return None
    return _line_from_text(str(value))


async def fetch_account() -> dict[str, Any]:
    payload = await fetch_json("oddspapi", "/v4/account")
    return payload if isinstance(payload, dict) else {}


async def fetch_tournaments(**params: Any) -> list[dict[str, Any]]:
    payload = await fetch_json("oddspapi", "/v4/tournaments", {"sportId": SOCCER_SPORT_ID, **params})
    return payload if isinstance(payload, list) else []


async def target_tournament_ids() -> dict[str, int]:
    tournaments = await fetch_tournaments()
    result: dict[str, int] = {}
    for item in tournaments:
        slug = str(item.get("slug") or "")
        if slug in TARGET_TOURNAMENT_SLUGS and item.get("id") is not None:
            result[slug] = int(item["id"])
    return result


async def fetch_fixtures(**params: Any) -> list[NormalizedMatch]:
    payload = await fetch_json("oddspapi", "/v4/fixtures", {"sportId": SOCCER_SPORT_ID, **params})
    if not isinstance(payload, list):
        return []
    rows: list[NormalizedMatch] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        fixture_id = item.get("id") or item.get("fixtureId")
        home = item.get("homeTeam") or item.get("home") or {}
        away = item.get("awayTeam") or item.get("away") or {}
        competition = item.get("tournamentName") or item.get("tournament") or ""
        home_name = home.get("name") if isinstance(home, dict) else home
        away_name = away.get("name") if isinstance(away, dict) else away
        kickoff = item.get("startTime") or item.get("kickoff") or item.get("date")
        if fixture_id is None or not home_name or not away_name or not kickoff:
            continue
        rows.append(NormalizedMatch(str(fixture_id), str(competition), str(home_name), str(away_name), _iso(kickoff)))
    return rows


def _market_catalog(markets: list[dict[str, Any]]) -> tuple[dict[int, tuple[str, float | None, str, str]], dict[tuple[int, int], str]]:
    market_meta: dict[int, tuple[str, float | None, str, str]] = {}
    outcome_names: dict[tuple[int, int], str] = {}
    for market in markets:
        if not isinstance(market, dict):
            continue
        raw_market_id = market.get("id") if market.get("id") is not None else market.get("marketId")
        if raw_market_id is None:
            continue
        market_id = int(raw_market_id)
        market_name = str(market.get("marketName") or market.get("name") or market_id)
        handicap_value = _line_from_text(market_name)
        market_meta[market_id] = (market_name, handicap_value, str(market.get("period") or ""), str(market.get("marketType") or ""))
        for outcome in market.get("outcomes") or []:
            if isinstance(outcome, dict) and outcome.get("outcomeId") is not None:
                outcome_names[(market_id, int(outcome["outcomeId"]))] = str(outcome.get("outcomeName") or outcome["outcomeId"])
    return market_meta, outcome_names


def _canonical_market(market_name: str, market_type: str, period: str, selection: str) -> tuple[str, str]:
    canonical_market, canonical_selection = normalize_market(market_name, selection, period)
    known_bases = {"1x2", "double_chance", "asian_handicap", "goals", "btts", "corners", "cards"}
    current_base = canonical_market.rsplit("_", 1)[0]
    if current_base not in known_bases:
        type_aliases = {
            "1x2": "1x2", "totals": "goals", "total": "goals", "goals": "goals",
            "btts": "btts", "both_teams_to_score": "btts", "corners": "corners",
            "cards": "cards", "asian_handicap": "asian_handicap", "handicap": "asian_handicap",
            "spread": "asian_handicap",
        }
        base = type_aliases.get(str(market_type).strip().lower())
        if base:
            period_key = canonical_market.rsplit("_", 1)[-1]
            canonical_market = f"{base}_{period_key}"
            if base in {"goals", "corners", "cards", "btts"}:
                if canonical_selection in {"o", "over"}:
                    canonical_selection = "over" if base != "btts" else "yes"
                elif canonical_selection in {"u", "under"}:
                    canonical_selection = "under" if base != "btts" else "no"
    return canonical_market, canonical_selection


def parse_odds(payload: dict[str, Any], *, bookmaker: str = ODDSPAPI_BETANO_PE, market_catalog: list[dict[str, Any]] | None = None) -> list[NormalizedOdd]:
    fixture_id = payload.get("fixtureId")
    if fixture_id is None:
        return []
    market_meta, outcome_names = _market_catalog(market_catalog or [])
    bookmaker_data = (payload.get("bookmakerOdds") or {}).get(bookmaker)
    if not isinstance(bookmaker_data, dict) or bookmaker_data.get("suspended") or not bookmaker_data.get("bookmakerIsActive", True):
        return []
    captured = _iso(payload.get("updatedAt"))
    rows: list[NormalizedOdd] = []
    for market_id, market in (bookmaker_data.get("markets") or {}).items():
        if not isinstance(market, dict) or not market.get("marketActive", True):
            continue
        try:
            market_id_int = int(market_id)
        except (TypeError, ValueError):
            market_id_int = 0
        meta = market_meta.get(market_id_int)
        market_name = meta[0] if meta else f"market:{market_id}"
        catalog_line = meta[1] if meta else None
        period = meta[2] if meta else ""
        market_type = meta[3] if meta else ""
        for outcome_id, outcome in (market.get("outcomes") or {}).items():
            if not isinstance(outcome, dict):
                continue
            try:
                outcome_id_int = int(outcome_id)
            except (TypeError, ValueError):
                outcome_id_int = 0
            selection_name = outcome_names.get((market_id_int, outcome_id_int), str(outcome_id))
            for player in (outcome.get("players") or {}).values():
                if not isinstance(player, dict) or not player.get("active", True):
                    continue
                try:
                    price = float(player["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price <= 1:
                    continue
                outcome_key = player.get("bookmakerOutcomeId") or selection_name
                line = _line_from_outcome_id(outcome_key)
                if line is None:
                    line = catalog_line
                selection = selection_name
                if player.get("playerName"):
                    selection = f"{selection_name}:{player['playerName']}"
                canonical_market, canonical_selection = _canonical_market(market_name, market_type, period, selection)
                rows.append(NormalizedOdd(str(fixture_id), bookmaker, canonical_market, canonical_selection, price, _iso(player.get("changedAt")) if player.get("changedAt") else captured, line))
    return rows


async def fetch_market_catalog(*, force: bool = False) -> list[dict[str, Any]]:
    global _MARKET_CATALOG_CACHE, _MARKET_CATALOG_CACHE_AT
    now = datetime.now(timezone.utc)
    if not force and _MARKET_CATALOG_CACHE is not None and _MARKET_CATALOG_CACHE_AT is not None:
        age = (now - _MARKET_CATALOG_CACHE_AT).total_seconds()
        if age < _MARKET_CATALOG_TTL_SECONDS:
            return _MARKET_CATALOG_CACHE
    payload = await fetch_json("oddspapi", "/v4/markets", {"language": "en"})
    _MARKET_CATALOG_CACHE = payload if isinstance(payload, list) else []
    _MARKET_CATALOG_CACHE_AT = now
    return _MARKET_CATALOG_CACHE


async def fetch_odds(fixture_id: str, *, bookmaker: str = ODDSPAPI_BETANO_PE, market_catalog: list[dict[str, Any]] | None = None) -> list[NormalizedOdd]:
    payload = await fetch_json("oddspapi", "/v4/odds", {"fixtureId": fixture_id, "bookmakers": bookmaker, "oddsFormat": "decimal", "language": "en"})
    return parse_odds(payload if isinstance(payload, dict) else {}, bookmaker=bookmaker, market_catalog=market_catalog)
