"""Tests for the arbitrage engine: pre-match, live, stale-odds and scope filters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from betano_analyzer.arbitrage import find_arbitrage, _is_live, _is_stale_live, _is_peru_competition
from betano_analyzer.db import connect, initialize


def _seed_match_with_odds(
    kickoff: str,
    suffix: str,
    status: str = "scheduled",
    competition: str = "premier league",
    bookmakers: tuple[str, str, str] = ("BookA", "BookB", "BookC"),
):
    initialize()
    external_id = f"test-arb-{suffix}"
    with connect() as db:
        db.execute("DELETE FROM odds WHERE match_id IN (SELECT id FROM matches WHERE external_id=?)", (external_id,))
        db.execute("DELETE FROM matches WHERE external_id=?", (external_id,))
        cur = db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            (external_id, competition, "Alpha", "Beta", kickoff, status),
        )
        match_id = cur.lastrowid
        rows = [
            (match_id, bookmakers[0], "1x2_ft", "home", 2.20),
            (match_id, bookmakers[1], "1x2_ft", "draw", 4.20),
            (match_id, bookmakers[2], "1x2_ft", "away", 4.20),
        ]
        for row in rows:
            db.execute(
                "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
                (*row, datetime.now(timezone.utc).isoformat(), None),
            )
        db.commit()
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


def test_pre_match_ignores_stale_high_odds_when_newer_price_is_not_arbitrage():
    kickoff = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "stale")
    now = datetime.now(timezone.utc)
    with connect() as db:
        db.execute(
            "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
            (match_id, "BookA", "1x2_ft", "home", 1.70, (now + timedelta(seconds=1)).isoformat(), None),
        )
        db.commit()
    assert find_arbitrage(live=False, match_id=match_id) == []


def test_live_stale_odds_rejected(monkeypatch):
    monkeypatch.setenv("LIVE_STALE_MINUTES", "15")
    kickoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "stalive", status="live")
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    with connect() as db:
        db.execute("UPDATE odds SET captured_at=? WHERE match_id=?", (stale_time, match_id))
        db.commit()
    assert find_arbitrage(live=True, match_id=match_id) == []


def test_live_fresh_odds_accepted(monkeypatch):
    monkeypatch.setenv("LIVE_STALE_MINUTES", "15")
    kickoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "freshlive", status="live")
    result = find_arbitrage(live=True, match_id=match_id)
    assert len(result) == 1
    assert result[0].mode == "live"


def test_scope_separates_peru_from_world():
    kickoff = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    # Peru scope must contain only bookmakers classified as PERU.
    peru_id = _seed_match_with_odds(
        kickoff,
        "peru-scope",
        competition="liga 1 peru",
        bookmakers=("Betano", "Apuesta Total", "Inkabet"),
    )
    world_id = _seed_match_with_odds(
        kickoff,
        "world-scope",
        competition="premier league",
        bookmakers=("Betano", "Pinnacle", "bet365"),
    )

    peru = find_arbitrage(live=False, scope="peru")
    world = find_arbitrage(live=False, scope="world")
    peru_ids = {item.match_id for item in peru}
    world_ids = {item.match_id for item in world}

    assert peru_id in peru_ids
    assert world_id not in peru_ids
    assert world_id in world_ids
    assert peru_id not in world_ids
    peru_item = next(item for item in peru if item.match_id == peru_id)
    world_item = next(item for item in world if item.match_id == world_id)
    assert peru_item.scope == "peru"
    assert world_item.scope == "world"
    assert peru_item.competition == "liga 1 peru"
    assert all(item["classification"] == "PERU" for item in peru_item.outcomes.values())


def test_league_filter_returns_only_selected_league():
    kickoff = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    liga1_id = _seed_match_with_odds(
        kickoff,
        "league-1",
        competition="liga 1 peru",
        bookmakers=("Betano", "Apuesta Total", "Inkabet"),
    )
    liga2_id = _seed_match_with_odds(
        kickoff,
        "league-2",
        competition="liga 2 peru",
        bookmakers=("Betano", "Apuesta Total", "Inkabet"),
    )
    result = find_arbitrage(live=False, scope="peru", league="liga 1")
    ids = {item.match_id for item in result}
    assert liga1_id in ids
    assert liga2_id not in ids


def test_peru_competition_classifier():
    assert _is_peru_competition("Liga 1 Peru")
    assert _is_peru_competition("Copa Perú")
    assert _is_peru_competition("Segunda División Peru")
    assert not _is_peru_competition("Premier League")


def test_is_stale_live_logic():
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(minutes=5)).isoformat()
    stale = (now - timedelta(minutes=20)).isoformat()
    assert not _is_stale_live(fresh, now, 15)
    assert _is_stale_live(stale, now, 15)
    assert _is_stale_live(None, now, 15)
    assert _is_stale_live("invalid-ts", now, 15)


def test_is_live_uses_status_before_kickoff():
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert _is_live(future, status="live") is True
    assert _is_live(future, status="scheduled") is False


def test_is_live_falls_back_to_kickoff_when_status_unknown():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert _is_live(past, status="") is True
    assert _is_live(future, status="") is False
