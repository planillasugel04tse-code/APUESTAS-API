from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any


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
    ProviderConfig(
        name="odds-api-io",
        kind="odds",
        base_url="https://api.odds-api.io",
        api_key_env="ODDS_API_IO_KEY",
        enabled=False,
    ),
    ProviderConfig(
        name="oddspapi",
        kind="odds",
        base_url="https://api.oddspapi.com",
        api_key_env="ODDSPAPI_KEY",
        enabled=False,
    ),
)


def provider_status() -> list[dict[str, Any]]:
    return [
        {
            "name": provider.name,
            "kind": provider.kind,
            "base_url": provider.base_url,
            "enabled": provider.enabled,
            "configured": provider.configured,
            "api_key_env": provider.api_key_env,
        }
        for provider in DEFAULT_PROVIDERS
    ]
