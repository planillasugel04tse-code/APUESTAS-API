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
    live_only: bool = False,
) -> SyncSummary:
    """Import a bounded Betano PE window through OddsPapi.

    When ``live_only`` is true, only live fixtures are requested. This is used
    by the on-demand live surebet button so normal dashboard loads do not
    consume live odds calls.
    """
    if hours < 1 or hours > 48:
        raise ValueError("hours debe estar entre 1 y 48")
    if limit_matches < 1 or limit_matches > 50:
        raise ValueError("limit_matches debe estar entre 1 y 50")
    if live_only and not include_live:
        include_live = True

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    statuses = [1] if live_only else ([0, 1] if include_live else [0])

    market_catalog = await fetch_market_catalog()
    pending_matches = []
    live_matches = []
    for status_id in statuses:
        found = await fetch_fixtures(
            from_time=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            to_time=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            status_id=status_id,
            bookmaker=ODDSPAPI_BETANO_PE,
        )
        if status_id == 1:
            live_matches.extend(found)
        else:
            pending_matches.extend(found)

    all_matches = pending_matches + live_matches
    unique = {match.external_id: match for match in filter_competitions(all_matches)}
    selected_matches = list(unique.values())[:limit_matches]
    selected_live_ids = {match.external_id for match in live_matches} & set(unique)

    matches_seen, matches_saved = save_matches(selected_matches)

    odds = []
    for match in selected_matches:
        odds.extend(await fetch_odds(match.external_id, bookmaker=ODDSPAPI_BETANO_PE, market_catalog=market_catalog))
    odds_seen, odds_saved = save_odds(odds)

    live_seen = sum(match.external_id in selected_live_ids for match in selected_matches)
    return SyncSummary(
        leagues=8,
        matches_seen=matches_seen,
        matches_saved=matches_saved,
        odds_seen=odds_seen,
        odds_saved=odds_saved,
        live_matches_seen=live_seen,
        live_matches_saved=live_seen,
    )
