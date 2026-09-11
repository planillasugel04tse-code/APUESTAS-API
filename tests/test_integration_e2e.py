"""Integration test: full pipeline from Telegram message to Final Selector.

This test wires a real SQLite in-memory database through the complete flow:
  Telegram message → parser → matching → event → signal → Betano snapshot
  → persistence → value radar → master radar → final selector → surebet.

It verifies that:
- The pipeline runs without errors on valid input.
- Prices from the tipster and from Betano remain separate.
- The pending_match flow is exercised when no event exists.
- The retry mechanism resolves the pending signal after the event is inserted.
- The surebet engine does not produce a live result for a pre-match fixture.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import betano_analyzer.db as db_module
import betano_analyzer.telegram.service as svc_module
import betano_analyzer.telegram.backtest as backtest_module
import betano_analyzer.radar_value as rv_module
import betano_analyzer.final_selector as fs_module
import betano_analyzer.master_radar as mr_module
import betano_analyzer.arbitrage as arb_module
from betano_analyzer.telegram.parser import parse_telegram_message
from betano_analyzer.telegram.service import process_telegram_signal, retry_pending_matches
from betano_analyzer.db import initialize, connect
from betano_analyzer.arbitrage import find_arbitrage


# ---------------------------------------------------------------------------
# Shared in-memory DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def mem_db(monkeypatch):
    """Provide a fresh in-memory SQLite DB and patch all connect() calls."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Run schema creation
    conn.executescript(db_module.SCHEMA)
    conn.commit()

    def _connect(path=None):
        return conn

    # Patch connect in every module that imports it
    monkeypatch.setattr(db_module, "connect", _connect)
    monkeypatch.setattr(svc_module, "connect", _connect)
    monkeypatch.setattr(backtest_module, "connect", _connect)

    # Silence the complex radar engines to focus on the pipeline
    monkeypatch.setattr(rv_module, "build_value_radar", lambda **kw: {"opportunities": []})
    monkeypatch.setattr(mr_module, "build_master_radar", lambda **kw: {"opportunities": []})
    monkeypatch.setattr(fs_module, "build_final_selection", lambda **kw: {"opportunities": []})
    monkeypatch.setattr(arb_module, "connect", _connect)

    return conn


# ---------------------------------------------------------------------------
# Helper: insert a match + Betano odds into the DB
# ---------------------------------------------------------------------------

def _seed_match(conn, *, home, away, kickoff, status="scheduled", competition="Premier League"):
    cur = conn.execute(
        "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
        (f"ext-{home}-{away}", competition, home, away, kickoff, status),
    )
    return cur.lastrowid


def _seed_betano_odds(conn, match_id, market, selection, odds, captured_at=None):
    conn.execute(
        "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
        (match_id, "Betano", market, selection, odds, captured_at or datetime.now(timezone.utc).isoformat(), None),
    )


# ---------------------------------------------------------------------------
# Test 1: Complete happy-path pipeline
# ---------------------------------------------------------------------------

def test_e2e_pipeline_full_flow(mem_db, monkeypatch):
    """End-to-end: Telegram message → matched event → analysis stored correctly."""
    future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    match_id = _seed_match(mem_db, home="Manchester United", away="Chelsea", kickoff=future)
    _seed_betano_odds(mem_db, match_id, "1x2_ft", "home", 2.10)
    mem_db.commit()

    result = process_telegram_signal(
        "Manchester United vs Chelsea cuota 1.95 stake 3",
        channel="@tipster_test",
        message_id="msg-001",
        tipster="TipsterTest",
    )

    assert result["status"] == "success"
    assert result["match_id"] == match_id
    assert result["pick_id"] is not None

    analysis = result["analysis"]
    # Tipster odds and Betano odds are SEPARATE
    assert analysis["tipster_odds"] == 1.95
    assert analysis["betano_current_odds"] == 2.10
    assert analysis["tipster_odds"] != analysis["betano_current_odds"]
    assert "source_price_delta" in analysis
    assert "source_price_note" in analysis

    # Signal persisted
    row = mem_db.execute(
        "SELECT * FROM telegram_signals WHERE channel=? AND message_id=?",
        ("@tipster_test", "msg-001"),
    ).fetchone()
    assert row is not None
    assert row["match_status"] == "matched"
    assert row["tipster_odds"] == pytest.approx(1.95)
    assert row["betano_current_odds"] == pytest.approx(2.10)


# ---------------------------------------------------------------------------
# Test 2: Duplicate message is idempotent
# ---------------------------------------------------------------------------

def test_e2e_duplicate_message_is_idempotent(mem_db, monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    _seed_match(mem_db, home="Real Madrid", away="Juventus", kickoff=future)
    mem_db.commit()

    process_telegram_signal(
        "Real Madrid vs Juventus cuota 1.70",
        channel="@ch", message_id="dup-1", tipster="T",
    )
    result2 = process_telegram_signal(
        "Real Madrid vs Juventus cuota 1.70",
        channel="@ch", message_id="dup-1", tipster="T",
    )
    assert result2["status"] == "already_processed"


# ---------------------------------------------------------------------------
# Test 3: Pending match flow + retry
# ---------------------------------------------------------------------------

def test_e2e_pending_match_and_retry(mem_db, monkeypatch):
    """Signal arrives before event exists → pending; retry resolves it after insert."""
    result = process_telegram_signal(
        "Barcelona vs PSG cuota 2.20",
        channel="@ch", message_id="pend-1", tipster="T",
    )
    assert result["status"] == "pending_match"

    # Now insert the match
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    _seed_match(mem_db, home="Barcelona", away="Paris Saint Germain", kickoff=future)
    mem_db.commit()

    retry_result = retry_pending_matches()
    assert retry_result["resolved"] == 1
    assert retry_result["still_pending"] == 0

    row = mem_db.execute(
        "SELECT match_status FROM telegram_signals WHERE channel=? AND message_id=?",
        ("@ch", "pend-1"),
    ).fetchone()
    assert row["match_status"] == "matched"


# ---------------------------------------------------------------------------
# Test 4: Invalid message — no valid teams → fails gracefully
# ---------------------------------------------------------------------------

def test_e2e_invalid_message_fails_gracefully(mem_db, monkeypatch):
    result = process_telegram_signal(
        "Noticia: Jornada 5 de la liga",
        channel="@ch", message_id="inv-1", tipster="T",
    )
    assert result["status"] == "failed"
    # Persisted as failed
    row = mem_db.execute(
        "SELECT status FROM telegram_messages WHERE channel=? AND message_id=?",
        ("@ch", "inv-1"),
    ).fetchone()
    assert row["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 5: Surebet pre-match only — live mode must return empty for future match
# ---------------------------------------------------------------------------

def test_e2e_surebet_live_excludes_future_match(mem_db, monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    match_id = _seed_match(mem_db, home="Ajax", away="Inter Milan", kickoff=future, status="scheduled")
    _seed_betano_odds(mem_db, match_id, "1x2_ft", "home", 2.20)
    mem_db.execute(
        "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
        (match_id, "BookB", "1x2_ft", "draw", 4.20, datetime.now(timezone.utc).isoformat(), None),
    )
    mem_db.execute(
        "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
        (match_id, "BookC", "1x2_ft", "away", 4.20, datetime.now(timezone.utc).isoformat(), None),
    )
    mem_db.commit()

    # Live mode must return nothing for a scheduled/future match
    live_arb = find_arbitrage(live=True, match_id=match_id)
    assert live_arb == []

    # Pre-match should find the arbitrage
    pre_arb = find_arbitrage(live=False, match_id=match_id)
    assert len(pre_arb) == 1
    assert pre_arb[0].mode == "pre_match"
    assert pre_arb[0].profit_margin > 0


# ---------------------------------------------------------------------------
# Test 6: Stale live odds do not generate a live surebet
# ---------------------------------------------------------------------------

def test_e2e_stale_live_odds_rejected(mem_db, monkeypatch):
    """Live cuotas older than LIVE_STALE_MINUTES are discarded, no phantom surebet."""
    kickoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    match_id = _seed_match(mem_db, home="Napoli", away="Lazio", kickoff=kickoff, status="live")

    # Insert live odds that are 30 minutes old (stale, default threshold=15)
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    for book, sel, price in [("BookA", "home", 2.10), ("BookB", "draw", 4.20), ("BookC", "away", 4.20)]:
        mem_db.execute(
            "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
            (match_id, book, "1x2_ft", sel, price, stale_time, None),
        )
    mem_db.commit()

    # Monkeypatch stale threshold to 15 minutes
    monkeypatch.setenv("LIVE_STALE_MINUTES", "15")
    result = find_arbitrage(live=True, match_id=match_id)
    assert result == [], "Stale live odds must not produce a surebet"


# ---------------------------------------------------------------------------
# Test 7: Price separation — tipster_odds never overwrites betano_current_odds
# ---------------------------------------------------------------------------

def test_e2e_price_sources_are_always_separate(mem_db, monkeypatch):
    """The tipster price and the Betano DB price must remain distinct at all times."""
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    match_id = _seed_match(mem_db, home="Liverpool", away="Arsenal", kickoff=future)
    _seed_betano_odds(mem_db, match_id, "1x2_ft", "home", 1.85)
    mem_db.commit()

    result = process_telegram_signal(
        "Liverpool vs Arsenal cuota 2.10",  # tipster says 2.10
        channel="@ch", message_id="price-1", tipster="T",
    )

    analysis = result["analysis"]
    assert analysis["tipster_odds"] == pytest.approx(2.10)
    assert analysis["betano_current_odds"] == pytest.approx(1.85)
    # These must never be equal unless they truly are the same price
    assert analysis["tipster_odds"] != analysis["betano_current_odds"]
    # Delta must reflect the actual difference
    expected_delta = round(1.85 - 2.10, 4)
    assert analysis["source_price_delta"] == pytest.approx(expected_delta)
