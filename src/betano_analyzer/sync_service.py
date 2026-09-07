from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .ingestion_service import save_matches, save_odds
from .ingest import filter_competitions
from .oddspapi_io import ODDSPAPI_BETANO_PE, fetch_fixtures, fetch_market_catalog, fetch_odds
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


async def sync_oddspapi_betano_pe(
    *,
    hours: int = 48,
    limit_matches: int = 20,
    include_live: bool = False,
) -> SyncSummary:
    """Import a bounded Betano PE window through OddsPapi.

    The bounded limit is intentional: each fixture odds request is a billable
    API call on OddsPapi, so the sync should be predictable and safe to run
    manually from the local dashboard.
    """
    if hours < 1 or hours > 48:
        raise ValueError("hours debe estar entre 1 y 48")
    if limit_matches < 1 or limit_matches > 50:
        raise ValueError("limit_matches debe estar entre 1 y 50")

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    statuses = [0, 1] if include_live else [0]

    # One catalog request is reused for every fixture. OddsPapi documents the
    # market catalog as the source of market name, handicap and period metadata.
    market_catalog = await fetch_market_catalog()
    matches = []
    for status_id in statuses:
        matches.extend(
            await fetch_fixtures(
                from_time=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                to_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_id=status_id,
                bookmaker=ODDSPAPI_BETANO_PE,
            )
        )

    # De-duplicate in case a provider changes status while the two calls run.
    unique = {match.external_id: match for match in filter_competitions(matches)}
    selected_matches = list(unique.values())[:limit_matches]
    matches_seen, matches_saved = save_matches(selected_matches)

    odds = []
    for match in selected_matches:
        odds.extend(
            await fetch_odds(
                match.external_id,
                bookmaker=ODDSPAPI_BETANO_PE,
                market_catalog=market_catalog,
            )
        )
    odds_seen, odds_saved = save_odds(odds)

    live_count = sum(1 for match in selected_matches if match in matches and include_live)
    return SyncSummary(
        leagues=8,
        matches_seen=matches_seen,
        matches_saved=matches_saved,
        odds_seen=odds_seen,
        odds_saved=odds_saved,
        live_matches_seen=live_count,
        live_matches_saved=live_count,
    )
