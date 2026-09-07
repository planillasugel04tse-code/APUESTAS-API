from __future__ import annotations

from dataclasses import dataclass

from .ingestion_service import ImportSummary, import_normalized
from .odds_api_io import TARGET_LEAGUES, fetch_events, fetch_live_events, fetch_odds


@dataclass(frozen=True)
class SyncSummary:
    pre_match: ImportSummary
    live: ImportSummary
    odds_events: int


async def sync_odds_api(bookmakers: list[str] | None = None) -> SyncSummary:
    matches = []
    for league in TARGET_LEAGUES:
        matches.extend(await fetch_events(league, status="pending", limit=100))

    live = await fetch_live_events()
    all_matches = matches + live
    match_summary = import_normalized(all_matches, [])

    odds = []
    for match in all_matches:
        odds.extend(await fetch_odds(match.external_id, bookmakers))
    odds_summary = import_normalized([], odds)

    return SyncSummary(
        pre_match=match_summary,
        live=ImportSummary(len(live), len(live), 0, 0),
        odds_events=len(all_matches),
    )
