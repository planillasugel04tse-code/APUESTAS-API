from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .ingest import NormalizedMatch, NormalizedOdd


def _text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default


def adapt_generic_payload(payload: dict[str, Any], provider_name: str) -> tuple[list[NormalizedMatch], list[NormalizedOdd]]:
    """Adapt common event/odds payload shapes without pretending provider-specific schemas are identical.

    Provider-specific adapters can call this helper and map their response into `events` and `odds`.
    Unknown fields are ignored rather than guessed.
    """
    events = payload.get("events") or payload.get("matches") or []
    matches: list[NormalizedMatch] = []
    for event in events:
        home = event.get("home_team") or event.get("home")
        away = event.get("away_team") or event.get("away")
        external_id = event.get("id") or event.get("event_id")
        competition = event.get("competition") or event.get("league") or event.get("tournament")
        kickoff = event.get("kickoff") or event.get("start_time") or event.get("commence_time")
        if external_id and home and away and competition and kickoff:
            matches.append(NormalizedMatch(_text(external_id), _text(competition), _text(home), _text(away), _text(kickoff)))

    captured = datetime.now(timezone.utc).isoformat()
    odds_items = payload.get("odds") or []
    odds: list[NormalizedOdd] = []
    for item in odds_items:
        external_id = item.get("event_id") or item.get("match_id") or item.get("id")
        bookmaker = item.get("bookmaker") or provider_name
        market = item.get("market")
        selection = item.get("selection")
        price = item.get("odds") if item.get("odds") is not None else item.get("price")
        if external_id and market and selection and price:
            odds.append(NormalizedOdd(_text(external_id), _text(bookmaker), _text(market), _text(selection), float(price), _text(item.get("captured_at"), captured)))
    return matches, odds
