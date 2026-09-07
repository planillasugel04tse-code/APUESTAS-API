from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from .ingest import NormalizedMatch, NormalizedOdd, normalize_competition
from .providers import fetch_json


ODDSPAPI_BETANO_PE = "betano.pe"
SOCCER_SPORT_ID = 10

# OddsPapi tournament slugs currently used by the project. We resolve the numeric
# tournament IDs from the API instead of hard-coding them because IDs can change.
TARGET_TOURNAMENT_SLUGS = {
    "premier-league": "premier league",
    "laliga": "la liga",
    "serie-a": "serie a",
    "bundesliga": "bundesliga",
    "ligue-1": "ligue 1",
    "champions-league": "champions league",
    "europa-league": "europa league",
    "liga-1": "liga 1 peru",
}


def _iso(value: Any) -> str:
    return str(value) if value else datetime.now(timezone.utc).isoformat()


def _line_from_text(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"(?<!\d)(-?\d+(?:\.\d+)?)(?:/|\s|$)", str(value))
    return float(match.group(1)) if match else None


def _line_from_outcome_id(value: Any) -> float | None:
    if value is None:
        return None
    match = re.match(r"^(-?\d+(?:\.\d+)?)[/\\]", str(value))
    return float(match.group(1)) if match else None


async def fetch_account() -> dict[str, Any]:
    """Read OddsPapi quota/account state; this endpoint is not metered."""
    payload = await fetch_json("oddspapi", "/v4/account")
    return payload if isinstance(payload, dict) else {}


async def fetch_tournaments() -> list[dict[str, Any]]:
    payload = await fetch_json("oddspapi", "/v4/tournaments", {"sportId": SOCCER_SPORT_ID})
    return payload if isinstance(payload, list) else []


async def target_tournament_ids() -> dict[int, str]:
    result: dict[int, str] = {}
    for item in await fetch_tournaments():
        if not isinstance(item, dict) or item.get("tournamentId") is None:
            continue
        slug = str(item.get("tournamentSlug", "")).lower()
        if slug in TARGET_TOURNAMENT_SLUGS:
            result[int(item["tournamentId"])] = TARGET_TOURNAMENT_SLUGS[slug]
    return result


async def fetch_fixtures(
    *,
    from_time: str,
    to_time: str,
    status_id: int | None = None,
    bookmaker: str = ODDSPAPI_BETANO_PE,
) -> list[NormalizedMatch]:
    params: dict[str, Any] = {
        "sportId": SOCCER_SPORT_ID,
        "from": from_time,
        "to": to_time,
        "hasOdds": "true",
        "bookmakers": bookmaker,
    }
    if status_id is not None:
        params["statusId"] = status_id
    payload = await fetch_json("oddspapi", "/v4/fixtures", params)
    items = payload if isinstance(payload, list) else payload.get("fixtures", [])
    result: list[NormalizedMatch] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("tournamentSlug") or "").strip().lower()
        if slug not in TARGET_TOURNAMENT_SLUGS:
            continue
        tournament = str(item.get("tournamentName") or slug)
        competition = TARGET_TOURNAMENT_SLUGS[slug]
        if not item.get("fixtureId") or not item.get("participant1Name") or not item.get("participant2Name"):
            continue
        result.append(
            NormalizedMatch(
                str(item["fixtureId"]),
                normalize_competition(competition),
                str(item["participant1Name"]),
                str(item["participant2Name"]),
                _iso(item.get("startTime")),
            )
        )
    return result


def _market_catalog(
    catalog: list[dict[str, Any]],
) -> tuple[dict[int, tuple[str, float | None, str, str]], dict[tuple[int, int], str]]:
    """Return market metadata plus outcome labels.

    The handicap/line belongs to the market in OddsPapi's catalog for many
    markets (for example Over/Under 2.5), while some bookmaker outcome IDs also
    encode the line. We retain both so the parser can use the most precise value.
    """
    market_meta: dict[int, tuple[str, float | None, str, str]] = {}
    outcome_names: dict[tuple[int, int], str] = {}
    for market in catalog:
        if not isinstance(market, dict) or market.get("marketId") is None:
            continue
        market_id = int(market["marketId"])
        market_name = str(market.get("marketName") or market.get("marketType") or market_id)
        handicap = market.get("handicap")
        try:
            handicap_value = float(handicap) if handicap is not None else None
        except (TypeError, ValueError):
            handicap_value = _line_from_text(market_name)
        market_meta[market_id] = (
            market_name,
            handicap_value,
            str(market.get("period") or ""),
            str(market.get("marketType") or ""),
        )
        for outcome in market.get("outcomes") or []:
            if isinstance(outcome, dict) and outcome.get("outcomeId") is not None:
                outcome_names[(market_id, int(outcome["outcomeId"]))] = str(
                    outcome.get("outcomeName") or outcome["outcomeId"]
                )
    return market_meta, outcome_names


def parse_odds(
    payload: dict[str, Any],
    *,
    bookmaker: str = ODDSPAPI_BETANO_PE,
    market_catalog: list[dict[str, Any]] | None = None,
) -> list[NormalizedOdd]:
    fixture_id = payload.get("fixtureId")
    if fixture_id is None:
        return []
    market_meta, outcome_names = _market_catalog(market_catalog or [])
    bookmaker_data = (payload.get("bookmakerOdds") or {}).get(bookmaker)
    if not isinstance(bookmaker_data, dict):
        return []
    if bookmaker_data.get("suspended") or not bookmaker_data.get("bookmakerIsActive", True):
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
                rows.append(
                    NormalizedOdd(
                        str(fixture_id),
                        bookmaker,
                        market_name,
                        selection,
                        price,
                        _iso(player.get("changedAt")) if player.get("changedAt") else captured,
                        line,
                    )
                )
    return rows


async def fetch_market_catalog() -> list[dict[str, Any]]:
    payload = await fetch_json("oddspapi", "/v4/markets", {"language": "en"})
    return payload if isinstance(payload, list) else []


async def fetch_odds(
    fixture_id: str,
    *,
    bookmaker: str = ODDSPAPI_BETANO_PE,
    market_catalog: list[dict[str, Any]] | None = None,
) -> list[NormalizedOdd]:
    payload = await fetch_json(
        "oddspapi",
        "/v4/odds",
        {
            "fixtureId": fixture_id,
            "bookmakers": bookmaker,
            "oddsFormat": "decimal",
            "language": "en",
            "verbosity": 3,
        },
    )
    if not isinstance(payload, dict):
        return []
    return parse_odds(payload, bookmaker=bookmaker, market_catalog=market_catalog)
