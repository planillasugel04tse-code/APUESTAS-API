from __future__ import annotations

from typing import Any

# Separates legal status in Peru from OddsPapi availability.
# MINCETUR is the legal source of truth; OddsPapi availability is dynamic.
PERU_BOOKMAKER_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "brand": "Betano",
        "domain": "betano.pe",
        "oddspapi_slug": "betano.pe",
        "legal_status": "verified_register_2026-09",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "notes": "The MINCETUR-derived register data identifies KAIZEN GAMING PERU S.A.C. and sports authorization RD 1541-2024 dated 27/03/2024 as vigente.",
    },
    {
        "brand": "Apuesta Total",
        "domain": "apuestatotal.com",
        "oddspapi_slug": "apuestatotal",
        "legal_status": "verified_register_2026-09",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "notes": "The MINCETUR-derived register data identifies FREE GAMES S.A.C. and sports authorization RD 2656-2024 dated 24/05/2024 as vigente.",
    },
    {
        "brand": "Inkabet",
        "domain": "inkabet.pe",
        "oddspapi_slug": "inkabet",
        "legal_status": "verified_register_2026-09",
        "legal_source": "MINCETUR - Titulares de autorización de explotación",
        "notes": "The MINCETUR-derived register data identifies LUCKY TORITO S.A.C. and sports authorization RD 3859-2024 dated 09/07/2024 as vigente.",
    },
)

# Other operators with current Peru authorization evidence remain candidates
# until an exact OddsPapi Peru feed is confirmed. This prevents mixing a global
# feed with a locally authorized entity/domain.
PERU_LEGAL_CANDIDATES: tuple[str, ...] = (
    "Bet365",
    "Betsson",
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
