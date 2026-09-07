from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .ingest import NormalizedMatch, NormalizedOdd, normalize_competition
from .providers import fetch_json

TARGET_LEAGUES = {
    "england-premier-league": "premier league",
    "spain-la-liga": "la liga",
    "italy-serie-a": "serie a",
    "germany-bundesliga": "bundesliga",
    "france-ligue-1": "ligue 1",
    "international-uefa-champions-league": "champions league",
    "international-uefa-europa-league": "europa league",
    "peru-liga-1": "liga 1 peru",
}


def _iso(value: Any) -> str:
    return str(value) if value else datetime.now(timezone.utc).isoformat()


async def fetch_leagues() -> list[dict[str, Any]]:
    payload = await fetch_json("odds-api-io", "/v3/leagues", {"sport": "football", "all": "true"})
    return payload if isinstance(payload, list) else []


async def fetch_events(league: str, status: str = "pending", limit: int = 100) -> list[NormalizedMatch]:
    payload = await fetch_json("odds-api-io", "/v3/events", {"sport": "football", "league": league, "status": status, "limit": limit})
    items = payload if isinstance(payload, list) else payload.get("events", [])
    competition = TARGET_LEAGUES.get(league, normalize_competition(league))
    return [
        NormalizedMatch(str(item["id"]), competition, str(item["home"]), str(item["away"]), _iso(item.get("date")))
        for item in items
        if item.get("id") is not None and item.get("home") and item.get("away")
    ]


async def fetch_live_events() -> list[NormalizedMatch]:
    payload = await fetch_json("odds-api-io", "/v3/events/live", {"sport": "football"})
    items = payload if isinstance(payload, list) else payload.get("events", [])
    result: list[NormalizedMatch] = []
    for item in items:
        league = item.get("league") or {}
        slug = league.get("slug") if isinstance(league, dict) else str(league)
        if slug not in TARGET_LEAGUES:
            continue
        if item.get("id") is not None and item.get("home") and item.get("away"):
            result.append(NormalizedMatch(str(item["id"]), TARGET_LEAGUES[slug], str(item["home"]), str(item["away"]), _iso(item.get("date"))))
    return result


def _market_rows(event_id: str, data: dict[str, Any]) -> list[NormalizedOdd]:
    captured = datetime.now(timezone.utc).isoformat()
    rows: list[NormalizedOdd] = []
    for bookmaker, markets in (data.get("bookmakers") or {}).items():
        for market in markets or []:
            name = str(market.get("name", ""))
            updated = _iso(market.get("updatedAt"))
            for quote in market.get("odds") or []:
                for key, value in quote.items():
                    if key in {"hdp", "label"}:
                        continue
                    try:
                        price = float(value)
                    except (TypeError, ValueError):
                        continue
                    if price > 1:
                        selection = key
                        if quote.get("label"):
                            selection = f"{quote['label']}:{key}"
                        rows.append(NormalizedOdd(event_id, str(bookmaker), name, selection, price, updated or captured))
    return rows


async def fetch_odds(event_id: str, bookmakers: list[str] | None = None) -> list[NormalizedOdd]:
    params: dict[str, Any] = {"eventId": event_id}
    if bookmakers:
        params["bookmakers"] = ",".join(bookmakers)
    payload = await fetch_json("odds-api-io", "/v3/odds", params)
    return _market_rows(event_id, payload if isinstance(payload, dict) else {})


async def fetch_odds_multi(event_ids: list[str], bookmakers: list[str] | None = None) -> list[NormalizedOdd]:
    rows: list[NormalizedOdd] = []
    for start in range(0, len(event_ids), 10):
        batch = event_ids[start:start + 10]
        params: dict[str, Any] = {"eventIds": ",".join(batch)}
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)
        payload = await fetch_json("odds-api-io", "/v3/odds/multi", params)
        items = payload if isinstance(payload, list) else payload.get("events", []) if isinstance(payload, dict) else []
        if isinstance(payload, dict) and payload.get("id") is not None:
            items = [payload]
        for data in items:
            if isinstance(data, dict) and data.get("id") is not None:
                rows.extend(_market_rows(str(data["id"]), data))
    return rows
