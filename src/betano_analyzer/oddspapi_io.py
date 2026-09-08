from __future__ import annotations

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


_TYPE_ALIASES = {
    "1x2": "1x2",
    "totals": "goals",
    "total": "goals",
    "goals": "goals",
    "btts": "btts",
    "both_teams_to_score": "btts",
    "corners": "corners",
    "cards": "cards",
    "asian_handicap": "asian_handicap",
    "handicap": "asian_handicap",
    "spread": "asian_handicap",
}


def _period_key(period: str, fallback_market: str) -> str:
    text = str(period or "").strip().lower().replace("-", " ").replace("_", " ")
    if text in {"fulltime", "full time", "ft", "match", "90", "90 minutes"}:
        return "ft"
    if text in {"1h", "1st half", "first half", "firsthalf", "1 half"}:
        return "1h"
    if text in {"2h", "2nd half", "second half", "secondhalf", "2 half"}:
        return "2h"
    if "1st" in text or "first" in text:
        return "1h"
    if "2nd" in text or "second" in text:
        return "2h"
    if "_" in fallback_market:
        suffix = fallback_market.rsplit("_", 1)[-1]
        if suffix in {"ft", "1h", "2h"}:
            return suffix
    return "ft"


def _canonical_market(market_name: str, market_type: str, period: str, selection: str) -> tuple[str, str]:
    canonical_market, canonical_selection = normalize_market(market_name, selection, period)
    market_type_key = str(market_type or "").strip().lower()
    base = _TYPE_ALIASES.get(market_type_key)

    # OddsPapi's catalog marketType is authoritative when available. Some
    # catalog names normalize to market:<id>, which must never reach storage.
    if base:
        period_key = _period_key(period, canonical_market)
        canonical_market = f"{base}_{period_key}"

        selection_key = str(canonical_selection or "").strip().lower()
        if base == "1x2":
            selection_aliases = {
                "1": "home", "home": "home", "local": "home",
                "x": "draw", "draw": "draw", "tie": "draw",
                "2": "away", "away": "away", "visitor": "away",
            }
            canonical_selection = selection_aliases.get(selection_key, canonical_selection)
        elif base in {"goals", "corners", "cards"}:
            if selection_key in {"o", "over", "más", "mas"}:
                canonical_selection = "over"
            elif selection_key in {"u", "under", "menos"}:
                canonical_selection = "under"
        elif base == "btts":
            if selection_key in {"yes", "y", "si", "sí"}:
                canonical_selection = "yes"
            elif selection_key in {"no", "n"}:
                canonical_selection = "no"

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
