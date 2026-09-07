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
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    url = provider.base_url.rstrip("/") + "/" + path.lstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
