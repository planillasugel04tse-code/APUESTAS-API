from __future__ import annotations

import os
from typing import Any

from .peru_bookmakers import PERU_BOOKMAKER_REGISTRY, registry_slugs
from .providers import fetch_json

# The Peru shortlist is intentionally driven by the legal/API registry instead
# of a generic international bookmaker list.
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
            result.append(
                {
                    "name": str(name or slug),
                    "slug": str(slug or ""),
                    "live_odds": item.get("liveOdds"),
                    "clone_of": item.get("cloneOf"),
                }
            )
    return result


async def available_bookmakers() -> list[dict[str, Any]]:
    payload = await fetch_json("oddspapi", "/v4/bookmakers")
    return _rows(payload)


async def selected_bookmakers() -> list[str]:
    configured = os.getenv("ODDSPAPI_BOOKMAKERS", "").strip()
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    return list(registry_slugs())


async def peru_bookmakers() -> list[str]:
    available = await available_bookmakers()
    active_slugs = {row["slug"] for row in available if row.get("slug")}
    return [slug for slug in registry_slugs() if slug in active_slugs]


async def peru_bookmaker_catalog() -> dict[str, Any]:
    available = await available_bookmakers()
    by_slug = {row["slug"]: row for row in available if row.get("slug")}
    selected = set(await selected_bookmakers())
    rows: list[dict[str, Any]] = []

    for legal in PERU_BOOKMAKER_REGISTRY:
        slug = str(legal["oddspapi_slug"])
        feed = by_slug.get(slug)
        rows.append(
            {
                **legal,
                "available_in_oddspapi": feed is not None,
                "selected": slug in selected,
                "live_odds": feed.get("live_odds") if feed else None,
                "oddspapi_name": feed.get("name") if feed else None,
            }
        )

    return {
        "provider": "oddspapi",
        "market": "Peru",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "priority_bookmakers": rows,
        "available_peru_bookmakers": [row["oddspapi_slug"] for row in rows if row["available_in_oddspapi"]],
        "selected_bookmakers": sorted(selected),
        "selection_rule": "Legal/authorized Peru registry first; OddsPapi availability second.",
    }
