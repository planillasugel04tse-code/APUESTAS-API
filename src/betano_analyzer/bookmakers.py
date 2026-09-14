from __future__ import annotations

import os
import re
from typing import Any

from .peru_bookmakers import PERU_BOOKMAKER_REGISTRY, SUREBET_EXTRA_BOOKMAKERS, registry_slugs
from .providers import fetch_json

PERU_BOOKMAKERS = tuple(row["brand"] for row in PERU_BOOKMAKER_REGISTRY)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        name = item.get("bookmakerName") or item.get("name")
        if slug or name:
            result.append({"name": str(name or slug), "slug": str(slug or ""), "live_odds": item.get("liveOdds"), "clone_of": item.get("cloneOf")})
    return result


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


async def available_bookmakers() -> list[dict[str, Any]]:
    payload = await fetch_json("oddspapi", "/v4/bookmakers")
    return _rows(payload)


async def _dynamic_surebet_bookmakers() -> list[str]:
    available = await available_bookmakers()
    by_slug = {row["slug"]: row for row in available if row.get("slug")}
    normalized = {_norm(row.get("name")): row["slug"] for row in available if row.get("slug")}
    selected: list[str] = []
    for legal in PERU_BOOKMAKER_REGISTRY:
        slug = str(legal["oddspapi_slug"])
        if slug in by_slug:
            selected.append(slug)
        else:
            matched = normalized.get(_norm(legal["brand"]))
            if matched:
                selected.append(matched)
    for extra in SUREBET_EXTRA_BOOKMAKERS:
        if extra in by_slug:
            selected.append(extra)
        else:
            matched = normalized.get(_norm(extra))
            if matched:
                selected.append(matched)
    return list(dict.fromkeys(selected))


async def selected_bookmakers() -> list[str]:
    configured = os.getenv("ODDSPAPI_BOOKMAKERS", "").strip()
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    return await _dynamic_surebet_bookmakers()


async def peru_bookmakers() -> list[str]:
    return await _dynamic_surebet_bookmakers()


async def peru_bookmaker_catalog() -> dict[str, Any]:
    available = await available_bookmakers()
    by_slug = {row["slug"]: row for row in available if row.get("slug")}
    selected = set(await selected_bookmakers())
    rows: list[dict[str, Any]] = []
    for legal in PERU_BOOKMAKER_REGISTRY:
        slug = str(legal["oddspapi_slug"])
        feed = by_slug.get(slug)
        rows.append({**legal, "available_in_oddspapi": feed is not None, "selected": slug in selected, "live_odds": feed.get("live_odds") if feed else None, "oddspapi_name": feed.get("name") if feed else None})
    pinnacle = by_slug.get("pinnacle")
    return {
        "provider": "oddspapi",
        "market": "Peru",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "priority_bookmakers": rows,
        "available_peru_bookmakers": [row["oddspapi_slug"] for row in rows if row["available_in_oddspapi"]],
        "pinnacle": {"slug": "pinnacle", "available_in_oddspapi": pinnacle is not None, "selected_for_surebet": "pinnacle" in selected, "live_odds": pinnacle.get("live_odds") if pinnacle else None},
        "selected_bookmakers": sorted(selected),
        "selection_rule": "All configured Peru candidates exposed by OddsPapi, plus Pinnacle; availability is dynamic.",
    }
