from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import os

import httpx

from .ingest import NormalizedMatch, NormalizedOdd, filter_competitions, normalize_competition, normalize_market
from .providers import DEFAULT_PROVIDERS


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    matches: list[NormalizedMatch]
    odds: list[NormalizedOdd]


def _provider(name: str):
    for p in DEFAULT_PROVIDERS:
        if p.name == name:
            return p
    raise ValueError(f"Proveedor no registrado: {name}")


def fetch_json(provider_name: str, path: str, params: dict[str, Any] | None = None, timeout: float = 20.0) -> Any:
    provider = _provider(provider_name)
    if not provider.configured:
        raise RuntimeError(f"Proveedor {provider_name} no configurado. Define {provider.api_key_env} y habilítalo.")
    headers = {"Authorization": f"Bearer {os.environ[provider.api_key_env]}"}
    url = f"{provider.base_url.rstrip('/')}/{path.lstrip('/')}"
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params or {}, headers=headers)
        response.raise_for_status()
        return response.json()


def normalize_generic_payload(provider_name: str, payload: list[dict[str, Any]]) -> ProviderResponse:
    matches: list[NormalizedMatch] = []
    odds: list[NormalizedOdd] = []
    for item in payload:
        competition = normalize_competition(str(item.get("competition") or item.get("league") or ""))
        match_id = str(item.get("external_id") or item.get("id") or "")
        home = str(item.get("home_team") or item.get("home") or "")
        away = str(item.get("away_team") or item.get("away") or "")
        kickoff = str(item.get("kickoff") or item.get("start_time") or "")
        if match_id and home and away and kickoff:
            matches.append(NormalizedMatch(match_id, competition, home, away, kickoff))
        for odd in item.get("odds", []) or []:
            market, selection = normalize_market(str(odd.get("market") or ""), str(odd.get("selection") or ""))
            value = odd.get("odds")
            if match_id and value is not None:
                odds.append(NormalizedOdd(match_id, str(odd.get("bookmaker") or provider_name), market, selection, float(value), str(odd.get("captured_at") or kickoff)))
    return ProviderResponse(provider_name, filter_competitions(matches), odds)
