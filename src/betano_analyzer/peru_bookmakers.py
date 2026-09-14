from __future__ import annotations

from typing import Any

# Peru-focused candidate bookmakers. OddsPapi availability is checked dynamically.
PERU_BOOKMAKER_REGISTRY: tuple[dict[str, Any], ...] = (
    {"brand": "Betano", "domain": "betano.pe", "oddspapi_slug": "betano.pe", "legal_status": "verified_register_2026-09"},
    {"brand": "Apuesta Total", "domain": "apuestatotal.com", "oddspapi_slug": "apuestatotal", "legal_status": "verified_register_2026-09"},
    {"brand": "Inkabet", "domain": "inkabet.pe", "oddspapi_slug": "inkabet", "legal_status": "verified_register_2026-09"},
    {"brand": "Bet365", "domain": "bet365.com", "oddspapi_slug": "bet365", "legal_status": "candidate"},
    {"brand": "Betsson", "domain": "betsson.com", "oddspapi_slug": "betsson", "legal_status": "candidate"},
    {"brand": "Betcris", "domain": "betcris.com", "oddspapi_slug": "betcris", "legal_status": "candidate"},
    {"brand": "Te Apuesto", "domain": "teapuesto.com", "oddspapi_slug": "teapuesto", "legal_status": "candidate"},
    {"brand": "Stake", "domain": "stake.com", "oddspapi_slug": "stake", "legal_status": "candidate"},
    {"brand": "RushBet", "domain": "rushbet.co", "oddspapi_slug": "rushbet", "legal_status": "candidate"},
    {"brand": "Retabet", "domain": "retabet.es", "oddspapi_slug": "retabet", "legal_status": "candidate"},
    {"brand": "DoradoBet", "domain": "doradobet.com", "oddspapi_slug": "doradobet", "legal_status": "candidate"},
    {"brand": "Caliente", "domain": "caliente.mx", "oddspapi_slug": "caliente", "legal_status": "candidate"},
    {"brand": "Betsafe", "domain": "betsafe.com", "oddspapi_slug": "betsafe", "legal_status": "candidate"},
    {"brand": "1xBet", "domain": "1xbet.com", "oddspapi_slug": "1xbet", "legal_status": "candidate"},
    {"brand": "Pin-Up", "domain": "pin-up.bet", "oddspapi_slug": "pin-up", "legal_status": "candidate"},
)

# Requested additional sharp bookmaker. It is not classified as Peruvian.
SUREBET_EXTRA_BOOKMAKERS: tuple[str, ...] = ("pinnacle",)


def registry_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in PERU_BOOKMAKER_REGISTRY]


def registry_slugs() -> list[str]:
    return [str(row["oddspapi_slug"]) for row in PERU_BOOKMAKER_REGISTRY]
