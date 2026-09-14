from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .providers import fetch_json


@dataclass(frozen=True)
class CachedOdds:
    payload: Any
    expires_at: datetime


_CACHE: dict[tuple[str, tuple[str, ...], str, str, int], CachedOdds] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ttl_seconds() -> int:
    # Live prices need a short cache; callers can override per request.
    return 0


def _bookmaker_list(value: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    return tuple(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _cache_key(
    fixture_id: str,
    bookmakers: tuple[str, ...],
    language: str,
    odds_format: str,
    verbosity: int,
) -> tuple[str, tuple[str, ...], str, str, int]:
    return fixture_id, tuple(sorted(bookmakers)), language, odds_format, verbosity


async def get_bookmakers(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return the OddsPapi bookmaker catalogue."""
    key = ("__catalog__", (), "", "", 0)
    cached = _CACHE.get(key)
    if cached and not force_refresh and cached.expires_at > _now():
        return cached.payload
    payload = await fetch_json("oddspapi", "/v4/bookmakers")
    rows = payload if isinstance(payload, list) else []
    # Catalogue changes slowly; cache for six hours.
    _CACHE[key] = CachedOdds(rows, _now() + timedelta(hours=6))
    return rows


async def get_odds(
    fixture_id: str,
    *,
    bookmakers: str | list[str] | tuple[str, ...] | None = None,
    language: str = "es",
    odds_format: str = "decimal",
    verbosity: int = 3,
    cache_seconds: int = 0,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch one fixture from multiple bookmakers in a single billable call.

    A positive cache_seconds avoids spending a request when the same snapshot
    is requested repeatedly. Set force_refresh=True for an explicit refresh.
    """
    fixture_id = str(fixture_id).strip()
    if not fixture_id:
        raise ValueError("fixture_id es obligatorio")
    if cache_seconds < 0:
        raise ValueError("cache_seconds no puede ser negativo")

    bookmaker_tuple = _bookmaker_list(bookmakers)
    key = _cache_key(fixture_id, bookmaker_tuple, language, odds_format, verbosity)
    cached = _CACHE.get(key)
    if cached and not force_refresh and cached.expires_at > _now():
        return cached.payload

    params: dict[str, Any] = {
        "fixtureId": fixture_id,
        "language": language,
        "oddsFormat": odds_format,
        "verbosity": verbosity,
    }
    if bookmaker_tuple:
        params["bookmakers"] = ",".join(bookmaker_tuple)

    payload = await fetch_json("oddspapi", "/v4/odds", params=params)
    if cache_seconds > 0:
        _CACHE[key] = CachedOdds(payload, _now() + timedelta(seconds=cache_seconds))
    return payload


def clear_cache() -> None:
    _CACHE.clear()


def cache_info() -> dict[str, int]:
    now = _now()
    valid = sum(1 for item in _CACHE.values() if item.expires_at > now)
    return {"entries": len(_CACHE), "valid_entries": valid}
