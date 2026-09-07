from __future__ import annotations

from dataclasses import dataclass

from .ingestion_service import save_matches, save_odds
from .odds_api_io import TARGET_LEAGUES, fetch_events, fetch_live_events, fetch_odds_multi


@dataclass(frozen=True)
class SyncSummary:
    leagues: int
    matches_seen: int
    matches_saved: int
    odds_seen: int
    odds_saved: int
    live_matches_seen: int = 0
    live_matches_saved: int = 0


async def sync_odds(bookmakers: list[str], include_live: bool = False, limit_per_league: int = 100) -> SyncSummary:
    all_matches = []
    for league in TARGET_LEAGUES:
        all_matches.extend(await fetch_events(league, status="pending", limit=limit_per_league))

    matches_seen, matches_saved = save_matches(all_matches)
    event_ids = [m.external_id for m in all_matches]
    odds = await fetch_odds_multi(event_ids, bookmakers=bookmakers) if event_ids else []
    odds_seen, odds_saved = save_odds(odds)

    live_seen = live_saved = 0
    if include_live:
        live_matches = await fetch_live_events()
        live_seen, live_saved = save_matches(live_matches)
        if live_matches:
            live_odds = await fetch_odds_multi([m.external_id for m in live_matches], bookmakers=bookmakers)
            live_odds_seen, live_odds_saved = save_odds(live_odds)
            odds_seen += live_odds_seen
            odds_saved += live_odds_saved

    return SyncSummary(len(TARGET_LEAGUES), matches_seen, matches_saved, odds_seen, odds_saved, live_seen, live_saved)
