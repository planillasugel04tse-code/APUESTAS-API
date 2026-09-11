from __future__ import annotations

from typing import Any

from .providers import fetch_json

# Priority list for the Peru market. The aggregator is the source of truth for
# which of these are actually available to the configured API account.
PERU_BOOKMAKERS = (
    "Betano PE",
    "Betano",
    "Bet365",
    "Betsson",
    "Inkabet",
    "Apuesta Total",
    "Te Apuesto",
    "DoradoBet",
    "Betsafe",
    "Retabet ES",
    "1xbet",
    "Stake",
    "Meridianbet",
    "Coolbet",
    "Caliente",
)


def _names(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    result: list[str] = []
    for item in payload:
        if isinstance(item, dict) and item.get("name"):
            result.append(str(item["name"]))
    return result


async def available_bookmakers() -> list[dict[str, Any]]:
    payload = await fetch_json("odds-api-io", "/v3/bookmakers")
    if not isinstance(payload, list):
        return []
    return [
        {"name": str(item.get("name")), "active": bool(item.get("active", True))}
        for item in payload
        if isinstance(item, dict) and item.get("name")
    ]


async def selected_bookmakers() -> list[str]:
    payload = await fetch_json("odds-api-io", "/v3/bookmakers/selected")
    return _names(payload if isinstance(payload, list) else payload.get("bookmakers", []) if isinstance(payload, dict) else [])


async def peru_bookmakers() -> list[str]:
    available = await available_bookmakers()
    active = {str(item["name"]) for item in available if item.get("active", True)}
    # Exact names are required by Odds-API.io and are case-sensitive.
    return [name for name in PERU_BOOKMAKERS if name in active]


async def peru_bookmaker_catalog() -> dict[str, Any]:
    available = await available_bookmakers()
    active = {str(item["name"]) for item in available if item.get("active", True)}
    selected = set(await selected_bookmakers())
    rows = []
    for name in PERU_BOOKMAKERS:
        rows.append(
            {
                "name": name,
                "available": name in active,
                "selected_for_account": name in selected,
                "active": name in active,
            }
        )
    return {
        "provider": "odds-api-io",
        "market": "Peru",
        "priority_bookmakers": rows,
        "available_peru_bookmakers": [name for name in PERU_BOOKMAKERS if name in active],
        "selected_bookmakers": sorted(selected),
    }
