from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .db import connect
from .ingest import NormalizedMatch, NormalizedOdd, filter_competitions, normalize_competition, normalize_market


@dataclass(frozen=True)
class ImportSummary:
    matches_seen: int
    matches_saved: int
    odds_seen: int
    odds_saved: int


def save_matches(matches: Iterable[NormalizedMatch]) -> tuple[int, int]:
    items = filter_competitions(matches)
    saved = 0
    with connect() as db:
        for match in items:
            competition = normalize_competition(match.competition)
            existing = db.execute("SELECT id FROM matches WHERE external_id=?", (match.external_id,)).fetchone()
            if existing:
                db.execute("UPDATE matches SET competition=?,home_team=?,away_team=?,kickoff=? WHERE id=?", (competition, match.home_team, match.away_team, match.kickoff, existing["id"]))
            else:
                db.execute("INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,'scheduled')", (match.external_id, competition, match.home_team, match.away_team, match.kickoff))
                saved += 1
    return len(items), saved


def save_odds(odds: Iterable[NormalizedOdd]) -> tuple[int, int]:
    items = list(odds)
    saved = 0
    with connect() as db:
        for odd in items:
            match = db.execute("SELECT id FROM matches WHERE external_id=?", (odd.external_id,)).fetchone()
            if not match or odd.odds <= 1:
                continue
            market, selection = normalize_market(odd.market, odd.selection)
            db.execute("INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)", (match["id"], odd.bookmaker, market, selection, odd.odds, odd.captured_at, odd.line))
            saved += 1
    return len(items), saved


def import_normalized(matches: Iterable[NormalizedMatch], odds: Iterable[NormalizedOdd]) -> ImportSummary:
    matches = list(matches)
    odds = list(odds)
    match_seen, match_saved = save_matches(matches)
    odds_seen, odds_saved = save_odds(odds)
    return ImportSummary(match_seen, match_saved, odds_seen, odds_saved)
