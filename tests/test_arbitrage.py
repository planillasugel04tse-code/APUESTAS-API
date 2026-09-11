"""Tests for the arbitrage engine: pre-match, live, stale-odds and freshness checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from betano_analyzer.arbitrage import find_arbitrage, _is_live, _is_stale_live
from betano_analyzer.db import connect, initialize


def _seed_match_with_odds(kickoff: str, suffix: str, status: str = "scheduled"):
    initialize()
    external_id = f"test-arb-{suffix}"
    with connect() as db:
        db.execute("DELETE FROM odds WHERE match_id IN (SELECT id FROM matches WHERE external_id=?)", (external_id,))
        db.execute("DELETE FROM matches WHERE external_id=?", (external_id,))
        cur = db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            (external_id, "premier league", "Alpha", "Beta", kickoff, status),
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


# ---------------------------------------------------------------------------
# Pre-match tests
# ---------------------------------------------------------------------------

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

    assert find_arbitrage(live=False, match_id=match_id) == []


# ---------------------------------------------------------------------------
# Live freshness tests
# ---------------------------------------------------------------------------

def test_live_stale_odds_rejected(monkeypatch):
    """Cuotas live más antiguas que LIVE_STALE_MINUTES deben ser rechazadas."""
    monkeypatch.setenv("LIVE_STALE_MINUTES", "15")
    kickoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "stalive", status="live")

    # Overwrite the odds timestamps to be 30 minutes old (stale)
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    with connect() as db:
        db.execute("UPDATE odds SET captured_at=? WHERE match_id=?", (stale_time, match_id))

    result = find_arbitrage(live=True, match_id=match_id)
    assert result == [], "Stale live odds must not generate a surebet"


def test_live_fresh_odds_accepted(monkeypatch):
    """Cuotas live recientes (< LIVE_STALE_MINUTES) deben generar surebet si procede."""
    monkeypatch.setenv("LIVE_STALE_MINUTES", "15")
    kickoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    match_id = _seed_match_with_odds(kickoff, "freshlive", status="live")

    # Timestamps are already fresh (inserted just now)
    result = find_arbitrage(live=True, match_id=match_id)
    assert len(result) == 1
    assert result[0].mode == "live"


def test_is_stale_live_logic():
    """Unit test the staleness check function directly."""
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(minutes=5)).isoformat()
    stale = (now - timedelta(minutes=20)).isoformat()
    assert not _is_stale_live(fresh, now, 15)
    assert _is_stale_live(stale, now, 15)
    assert _is_stale_live(None, now, 15), "None timestamp must be treated as stale"
    assert _is_stale_live("invalid-ts", now, 15), "Invalid timestamp must be treated as stale"


# ---------------------------------------------------------------------------
# is_live classification tests
# ---------------------------------------------------------------------------

def test_is_live_uses_status_before_kickoff():
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert _is_live(future, status="live") is True
    assert _is_live(future, status="scheduled") is False


def test_is_live_falls_back_to_kickoff_when_status_unknown():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert _is_live(past, status="") is True
    assert _is_live(future, status="") is False


def test_is_live_finished_match_is_not_live():
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert _is_live(past, status="finished") is False
    assert _is_live(past, status="cancelled") is False
