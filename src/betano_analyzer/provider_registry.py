from __future__ import annotations

from dataclasses import asdict
from .ingest import SUPPORTED_COMPETITIONS, normalize_competition
from .providers import DEFAULT_PROVIDERS


def registry() -> dict:
    return {
        "football_only": True,
        "competitions": sorted(SUPPORTED_COMPETITIONS),
        "providers": [asdict(provider) for provider in DEFAULT_PROVIDERS],
        "normalization": {
            "competition_aliases": {
                "EPL": normalize_competition("EPL"),
                "LaLiga": normalize_competition("LaLiga"),
                "UEFA Champions League": normalize_competition("UEFA Champions League"),
                "Liga 1": normalize_competition("Liga 1"),
            }
        },
    }
