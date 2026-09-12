from __future__ import annotations

from collections import Counter
from typing import Any

from .providers import fetch_json


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _country_from_item(item: dict[str, Any]) -> str:
    for key in ("countryName", "country", "countryCode", "categoryName", "categorySlug", "regionName"):
        value = _text(item.get(key))
        if value:
            return value
    return "Desconocido"


async def scan_oddspapi_catalog(*, deep: bool = False, max_requests: int = 40) -> dict[str, Any]:
    """Analiza el catálogo disponible en la cuenta activa de OddsPapi.

    El modo catálogo usa tres llamadas medidas (sports/bookmakers/markets).
    El modo profundo añade torneos y fixtures dentro de un presupuesto explícito.
    Nunca intenta recorrer infinitamente el catálogo ni consumir la cuenta sin límite.
    """
    if max_requests < 3 or max_requests > 200:
        raise ValueError("max_requests debe estar entre 3 y 200")

    key = None
    from .provider_accounts import _read_accounts
    accounts = [a for a in _read_accounts() if a.get("active")]
    if accounts:
        key = str(accounts[0].get("api_key") or "").strip()
    if not key:
        import os
        key = os.getenv("ODDSPAPI_KEY", "").strip()
    if not key:
        raise RuntimeError("No hay una cuenta OddsPapi activa")

    requests_used = 0

    async def call(path: str, params: dict[str, Any] | None = None) -> Any:
        nonlocal requests_used
        if requests_used >= max_requests:
            raise StopAsyncIteration
        requests_used += 1
        import httpx
        url = "https://api.oddspapi.com/v4/" + path.lstrip("/")
        query = dict(params or {})
        query["apiKey"] = key
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(url, params=query, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()

    import httpx
    account_url = "https://api.oddspapi.com/v4/account"
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        account_response = await client.get(account_url, params={"apiKey": key}, headers={"Accept": "application/json"})
        account_response.raise_for_status()
        account = account_response.json()

    sports = await call("sports", {"language": "en"})
    bookmakers = await call("bookmakers")
    markets = await call("markets", {"language": "en"})

    sports = sports if isinstance(sports, list) else []
    bookmakers = bookmakers if isinstance(bookmakers, list) else []
    markets = markets if isinstance(markets, list) else []

    bookmaker_countries: Counter[str] = Counter(_country_from_item(b) for b in bookmakers if isinstance(b, dict))
    market_outcomes_by_market: dict[str, int] = {}
    market_types: Counter[str] = Counter()
    for market in markets:
        if not isinstance(market, dict):
            continue
        name = _text(market.get("marketName") or market.get("name") or market.get("marketSlug") or market.get("marketId")) or "Desconocido"
        outcomes = market.get("outcomes") or []
        market_outcomes_by_market[name] = len(outcomes) if isinstance(outcomes, list) else 0
        market_types[_text(market.get("marketType") or market.get("type") or "general")] += 1

    tournaments: list[dict[str, Any]] = []
    tournament_sports: Counter[str] = Counter()
    countries: Counter[str] = Counter()
    fixture_countries: Counter[str] = Counter()
    participant_names: set[str] = set()
    participant_ids: set[int] = set()
    fixture_ids: set[Any] = set()
    fixture_markets: Counter[str] = Counter()
    fixtures_seen = 0
    live_fixtures = 0
    upcoming_fixtures = 0
    stopped_reason = None

    if deep:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=48)
        for sport in sports:
            try:
                rows = await call("tournaments", {"sportId": sport.get("sportId"), "language": "en"})
            except StopAsyncIteration:
                stopped_reason = "Se alcanzó el presupuesto de solicitudes del escáner"
                break
            rows = rows if isinstance(rows, list) else []
            for row in rows:
                tournament_id = row.get("tournamentId")
                country = _country_from_item(row)
                sport_name = _text(sport.get("sportName") or sport.get("name") or sport.get("sportId")) or "Desconocido"
                tournaments.append({**row, "sportId": sport.get("sportId"), "sportName": sport_name})
                tournament_sports[sport_name] += 1
                countries[country] += 1
                if tournament_id is None:
                    continue
                try:
                    fixtures = await call(
                        "fixtures",
                        {
                            "tournamentId": tournament_id,
                            "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "language": "en",
                        },
                    )
                except StopAsyncIteration:
                    stopped_reason = "Se alcanzó el presupuesto de solicitudes del escáner"
                    break
                except httpx.HTTPStatusError:
                    continue
                if not isinstance(fixtures, list):
                    continue
                fixtures_seen += len(fixtures)
                for fixture in fixtures:
                    fixture_id = fixture.get("fixtureId") or fixture.get("id")
                    if fixture_id is not None:
                        fixture_ids.add(fixture_id)
                    fcountry = _country_from_item(fixture)
                    if fcountry != "Desconocido":
                        fixture_countries[fcountry] += 1
                    for field in ("participant1Id", "participant2Id"):
                        value = fixture.get(field)
                        if isinstance(value, int):
                            participant_ids.add(value)
                    for field in ("participant1Name", "participant2Name", "homeName", "awayName"):
                        value = _text(fixture.get(field))
                        if value:
                            participant_names.add(value)
                    status = fixture.get("statusId")
                    if status == 1:
                        live_fixtures += 1
                    elif status == 0:
                        upcoming_fixtures += 1
            if stopped_reason:
                break

    capabilities = {
        "live_odds": bool(account.get("has_live_odds")),
        "player_props": bool(account.get("has_player_props")),
        "websocket": bool(account.get("websocket_access") or account.get("has_websocket")),
        "historical_odds": True,
        "account_endpoint": "free/unmetered según la documentación del proveedor",
    }
    request_info = account.get("requests") if isinstance(account.get("requests"), dict) else {}

    return {
        "provider": "oddspapi",
        "scan": {
            "mode": "deep" if deep else "catalog",
            "requests_used_by_scanner": requests_used,
            "max_requests": max_requests,
            "stopped_reason": stopped_reason,
            "window_hours": 48 if deep else 0,
        },
        "account": account,
        "capabilities": capabilities,
        "request_info": request_info,
        "summary": {
            "sports": len(sports),
            "bookmakers": len(bookmakers),
            "bookmaker_countries": len(bookmaker_countries),
            "markets": len(markets),
            "market_outcomes": sum(market_outcomes_by_market.values()),
            "market_types": len(market_types),
            "tournaments": len(tournaments),
            "countries": len(countries),
            "fixtures_48h": fixtures_seen,
            "unique_fixture_ids_48h": len(fixture_ids),
            "participants_48h": max(len(participant_ids), len(participant_names)),
            "live_fixtures_48h": live_fixtures,
            "upcoming_fixtures_48h": upcoming_fixtures,
        },
        "sports": sports,
        "bookmakers": bookmakers,
        "bookmaker_countries": dict(bookmaker_countries),
        "markets": markets,
        "market_outcomes_by_market": market_outcomes_by_market,
        "market_types": dict(market_types),
        "tournaments": tournaments,
        "countries": dict(countries),
        "fixture_countries": dict(fixture_countries),
        "tournament_counts_by_sport": dict(tournament_sports),
        "participants_sample": sorted(participant_names)[:500],
    }
