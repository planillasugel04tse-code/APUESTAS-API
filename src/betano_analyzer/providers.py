from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx
from dotenv import load_dotenv

# Load a local .env before provider configuration is evaluated. This keeps
# Windows/local development consistent with CI and avoids requiring users to
# export secrets in every new terminal session.
load_dotenv()


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


def _enabled(env_name: str, key_env: str | None = None) -> bool:
    """Enable explicitly, or automatically when the provider key exists."""
    explicit = os.getenv(env_name)
    if explicit is not None:
        return explicit.strip().lower() in {"1", "true", "yes", "on"}
    return bool(key_env and os.getenv(key_env))


DEFAULT_PROVIDERS = (
    ProviderConfig(
        "odds-api-io",
        "odds",
        os.getenv("ODDS_API_IO_BASE_URL", "https://api.odds-api.io"),
        "ODDS_API_IO_KEY",
        _enabled("ODDS_API_IO_ENABLED", "ODDS_API_IO_KEY"),
    ),
    ProviderConfig(
        "oddspapi",
        "odds",
        os.getenv("ODDSPAPI_BASE_URL", "https://api.oddspapi.com"),
        "ODDSPAPI_KEY",
        _enabled("ODDSPAPI_ENABLED", "ODDSPAPI_KEY"),
    ),
)


def provider_status() -> list[dict[str, Any]]:
    return [
        {
            "name": p.name,
            "kind": p.kind,
            "base_url": p.base_url,
            "enabled": p.enabled,
            "configured": p.configured,
            "api_key_env": p.api_key_env,
        }
        for p in DEFAULT_PROVIDERS
    ]


def _config(name: str) -> ProviderConfig:
    for provider in DEFAULT_PROVIDERS:
        if provider.name == name:
            return provider
    raise ValueError(f"Proveedor no soportado: {name}")


async def fetch_json(
    provider_name: str,
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> Any:
    provider = _config(provider_name)
    if not provider.configured:
        raise RuntimeError(
            f"{provider.name} no está configurado. Activa el proveedor y define {provider.api_key_env}."
        )
    key = os.environ[provider.api_key_env]
    query = dict(params or {})
    # OddsPapi authenticates with the API key in the query string. Odds-API.io
    # also accepts apiKey as a query parameter, so one transport path works for
    # both providers used by the analyzer.
    query.setdefault("apiKey", key)
    url = provider.base_url.rstrip("/") + "/" + path.lstrip("/")
    # Avoid inheriting a system HTTP(S) proxy. On this Windows setup the
    # proxy path causes TLSV1_UNRECOGNIZED_NAME before reaching OddsPapi.
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.get(url, params=query, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
