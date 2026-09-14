from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .db import connect
from .ingestion_service import save_matches, save_odds
from .oddspapi_io import fetch_fixtures, fetch_market_catalog, fetch_odds
from .providers import fetch_json

SOCCER_SPORT_ID = 10
DEFAULT_BOOKMAKER_CAP = 10
INTERNAL_MATCH_BATCH = 20


@dataclass(frozen=True)
class GlobalLiveSyncSummary:
    bookmakers_discovered: int
    bookmakers_selected: int
    fixtures_seen: int
    fixtures_saved: int
    odds_seen: int
    odds_saved: int
    bookmaker_cap: int
    scope: str = "world"
    sport: str = "football"


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("bookmakers", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _bookmaker_key(item: dict[str, Any]) -> str | None:
    value = item.get("slug") or item.get("key") or item.get("bookmaker") or item.get("name")
    return str(value).strip() if value is not None and str(value).strip() else None


def _has_live_odds(item: dict[str, Any]) -> bool:
    value = item.get("has_live_odds")
    if value is None:
        value = item.get("hasLiveOdds")
    if value is None:
        value = item.get("liveOdds")
    return bool(value)


async def discover_live_bookmakers(limit: int = DEFAULT_BOOKMAKER_CAP) -> tuple[list[str], int]:
    payload = await fetch_json("oddspapi", "/v4/bookmakers")
    rows = _items(payload)
    candidates = []
    for item in rows:
        key = _bookmaker_key(item)
        if key and _has_live_odds(item):
            candidates.append(key)
    unique = list(dict.fromkeys(candidates))
    return unique[:limit], len(unique)


def _set_live_status(external_ids: set[str]) -> None:
    if not external_ids:
        return
    with connect() as db:
        placeholders = ",".join("?" for _ in external_ids)
        db.execute(
            f"UPDATE matches SET status='live' WHERE external_id IN ({placeholders})",
            tuple(sorted(external_ids)),
        )


async def sync_global_live(
    *,
    hours: int = 1,
    max_matches: int | None = None,
    bookmaker_cap: int = DEFAULT_BOOKMAKER_CAP,
) -> GlobalLiveSyncSummary:
    """Refresh worldwide live football odds with internal batching.

    ``max_matches`` is an internal safety control rather than a user-facing
    product limit. The scanner processes additional batches when required.
    """
    if hours < 1 or hours > 2:
        raise ValueError("hours debe estar entre 1 y 2 para el radar LIVE mundial")
    if max_matches is not None and max_matches < 1:
        raise ValueError("max_matches debe ser positivo")
    if bookmaker_cap < 1 or bookmaker_cap > 20:
        raise ValueError("bookmaker_cap debe estar entre 1 y 20")

    bookmakers, discovered = await discover_live_bookmakers(bookmaker_cap)
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    fixtures = await fetch_fixtures(
        from_time=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        to_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        status_id=1,
    )
    unique = list(dict.fromkeys((fixture.external_id, fixture) for fixture in fixtures))
    selected = [item[1] for item in unique]
    if max_matches is not None:
        selected = selected[:max_matches]
    seen, saved = save_matches(selected)
    _set_live_status({fixture.external_id for fixture in selected})

    catalog = await fetch_market_catalog()
    all_odds = []
    for start in range(0, len(selected), INTERNAL_MATCH_BATCH):
        batch = selected[start:start + INTERNAL_MATCH_BATCH]
        for bookmaker in bookmakers:
            for fixture in batch:
                all_odds.extend(
                    await fetch_odds(
                        fixture.external_id,
                        bookmaker=bookmaker,
                        market_catalog=catalog,
                    )
                )
    odds_seen, odds_saved = save_odds(all_odds)
    return GlobalLiveSyncSummary(
        bookmakers_discovered=discovered,
        bookmakers_selected=len(bookmakers),
        fixtures_seen=seen,
        fixtures_saved=saved,
        odds_seen=odds_seen,
        odds_saved=odds_saved,
        bookmaker_cap=bookmaker_cap,
    )
