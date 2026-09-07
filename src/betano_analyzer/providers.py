from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: str
    base_url: str | None
    api_key_env: str | None
    enabled: bool

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.base_url and self.api_key_env and os.getenv(self.api_key_env))


DEFAULT_PROVIDERS = (
    ProviderConfig("odds-api-io", "odds", "https://api.odds-api.io", "ODDS_API_IO_KEY", False),
    ProviderConfig("oddspapi", "odds", "https://api.oddspapi.com", "ODDSPAPI_KEY", False),
)


def provider_status() -> list[dict[str, Any]]:
    return [{"name": p.name, "kind": p.kind, "base_url": p.base_url, "enabled": p.enabled, "configured": p.configured, "api_key_env": p.api_key_env} for p in DEFAULT_PROVIDERS]


def _config(name: str) -> ProviderConfig:
    for provider in DEFAULT_PROVIDERS:
        if provider.name == name:
            return provider
    raise ValueError(f"Proveedor no soportado: {name}")


async def fetch_json(provider_name: str, path: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> Any:
    provider = _config(provider_name)
    if not provider.configured:
        raise RuntimeError(f"{provider.name} no está configurado. Activa el proveedor y define {provider.api_key_env}.")
    key = os.environ[provider.api_key_env]
    request_params = dict(params or {})
    request_params.setdefault("apiKey", key)
    url = provider.base_url.rstrip("/") + "/" + path.lstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params=request_params, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()


async def odds_api_io_events(league: str, status: str = "pending", limit: int = 100) -> Any:
    return await fetch_json("odds-api-io", "/v3/events", {"sport": "football", "league": league, "status": status, "limit": limit})


async def odds_api_io_live_events() -> Any:
    return await fetch_json("odds-api-io", "/v3/events/live", {"sport": "football"})


async def odds_api_io_odds(event_id: int, bookmakers: list[str]) -> Any:
    return await fetch_json("odds-api-io", "/v3/odds", {"eventId": event_id, "bookmakers": ",".join(bookmakers)})
