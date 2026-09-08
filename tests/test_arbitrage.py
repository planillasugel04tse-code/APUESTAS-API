from datetime import datetime, timedelta, timezone

from betano_analyzer.arbitrage import find_arbitrage
from betano_analyzer.db import connect, initialize


def _seed_match_with_odds(kickoff: str, suffix: str):
    initialize()
    external_id = f"test-arb-{suffix}"
    with connect() as db:
        db.execute("DELETE FROM odds WHERE match_id IN (SELECT id FROM matches WHERE external_id=?)", (external_id,))
        db.execute("DELETE FROM matches WHERE external_id=?", (external_id,))
        cur = db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            (external_id, "premier league", "Alpha", "Beta", kickoff, "scheduled"),
        )
        match_id = cur.lastrowid
        rows = [
            (match_id, "BookA", "1x2_ft", "home", 2.20),
            (match_id, "BookB", "1x2_ft", "draw", 4.20),
            (match_id, "BookC", "1x2_ft", "away", 4.20),
        ]
        for row in rows:
            db.execute(
                "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
                (*row, datetime.now(timezone.utc).isoformat(), None),
            )
        return match_id


def test_pre_match_surebet_accepts_period_suffixed_market():
    kickoff = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "prematch")

    result = find_arbitrage(live=False, match_id=match_id)

    assert len(result) == 1
    assert result[0].market == "1x2_ft"
    assert result[0].mode == "pre_match"
    assert result[0].profit_margin > 0


def test_live_mode_excludes_future_match():
    kickoff = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "future")

    assert find_arbitrage(live=True, match_id=match_id) == []
