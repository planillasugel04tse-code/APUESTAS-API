from __future__ import annotations

from collections import Counter
from typing import Any

from .providers import fetch_json


async def scan_oddspapi_catalog(*, deep: bool = False, max_requests: int = 40) -> dict[str, Any]:
    """Inspect the active OddsPapi account without requesting odds.

    The scanner deliberately counts every billable endpoint call and stops at
    max_requests. Account status itself is free, while sports/bookmakers/
    markets/tournaments/fixtures are billable according to OddsPapi docs.
    This prevents a free account from being drained by an accidental scan.
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
        # Use the provider transport but force the active account key.
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

    tournaments: list[dict[str, Any]] = []
    tournament_sports: Counter[str] = Counter()
    countries: Counter[str] = Counter()
    fixtures_seen = 0
    participants: set[int] = set()
    live_fixtures = 0
    upcoming_fixtures = 0
    stopped_reason = None

    # Deep mode walks tournaments and a 48-hour fixture window until the
    # request budget is reached. This produces real league/country/event data
    # while keeping the free account protected by an explicit request cap.
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
                country = row.get("categoryName") or row.get("categorySlug") or "Desconocido"
                tournaments.append({**row, "sportId": sport.get("sportId"), "sportName": sport.get("sportName")})
                tournament_sports[str(sport.get("sportName"))] += 1
                countries[str(country)] += 1
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
                    for field in ("participant1Id", "participant2Id"):
                        value = fixture.get(field)
                        if isinstance(value, int):
                            participants.add(value)
                    status = fixture.get("statusId")
                    if status == 1:
                        live_fixtures += 1
                    elif status == 0:
                        upcoming_fixtures += 1
            if stopped_reason:
                break

    return {
        "provider": "oddspapi",
        "scan": {
            "mode": "deep" if deep else "catalog",
            "requests_used_by_scanner": requests_used,
            "max_requests": max_requests,
            "stopped_reason": stopped_reason,
        },
        "account": account,
        "summary": {
            "sports": len(sports),
            "bookmakers": len(bookmakers),
            "markets": len(markets),
            "market_outcomes": sum(len(m.get("outcomes") or []) for m in markets if isinstance(m, dict)),
            "tournaments": len(tournaments),
            "countries": len(countries),
            "fixtures_48h": fixtures_seen,
            "participants_48h": len(participants),
            "live_fixtures_48h": live_fixtures,
            "upcoming_fixtures_48h": upcoming_fixtures,
        },
        "sports": sports,
        "bookmakers": bookmakers,
        "markets": markets,
        "tournaments": tournaments,
        "countries": dict(countries),
        "tournament_counts_by_sport": dict(tournament_sports),
    }
