from __future__ import annotations

from typing import Any

# Separates legal status in Peru from OddsPapi availability.
# MINCETUR is the legal source of truth; OddsPapi availability is dynamic.
PERU_BOOKMAKER_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "brand": "Betano",
        "domain": "betano.pe",
        "oddspapi_slug": "betano.pe",
        "legal_status": "verify_official_register",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "notes": "OddsPapi explicitly exposes the Betano PE feed; final legal status is checked against the live MINCETUR register.",
    },
    {
        "brand": "Apuesta Total",
        "domain": "apuestatotal.com",
        "oddspapi_slug": "apuestatotal",
        "legal_status": "verified_register_2026-09",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "notes": "September 2026 public-register checks identify Free Games S.A.C. and a vigente sports authorization.",
    },
    {
        "brand": "Inkabet",
        "domain": "inkabet.pe",
        "oddspapi_slug": "inkabet",
        "legal_status": "verified_register_2026-09",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "notes": "September 2026 public-register checks identify Lucky Torito S.A.C. and a vigente sports authorization.",
    },
)

# Other operators reported as Peru-authorized remain candidates until an exact
# OddsPapi Peru feed is confirmed. This prevents mixing a global feed with a
# locally authorized entity/domain.
PERU_LEGAL_CANDIDATES: tuple[str, ...] = (
    "Betcris",
    "Te Apuesto",
    "Stake",
    "RushBet",
    "Retabet",
    "DoradoBet",
    "Caliente",
)


def registry_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in PERU_BOOKMAKER_REGISTRY]


def registry_slugs() -> list[str]:
    return [str(row["oddspapi_slug"]) for row in PERU_BOOKMAKER_REGISTRY]
