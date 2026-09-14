"""Tests for the Telegram REST API endpoints.

Monkeypatching must target the names AS IMPORTED in telegram_api.py,
not the source module, because Python binds local references at import time.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

import betano_analyzer.db as db_mod
import betano_analyzer.telegram_api as tapi
from betano_analyzer.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def isolated_db(monkeypatch):
    """SQLite in-memory with check_same_thread=False for FastAPI TestClient threads."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(db_mod.SCHEMA)
    conn.commit()
    monkeypatch.setattr(db_mod, "connect", lambda path=None: conn)
    return conn


# ---------------------------------------------------------------------------
# POST /api/v1/telegram/signals
# ---------------------------------------------------------------------------

def test_ingest_signal_returns_failed_for_invalid_message(client, monkeypatch):
    monkeypatch.setattr(tapi, "process_telegram_signal", lambda *a, **kw: {
        "status": "failed", "signal_id": "tg-abc", "error": "Mensaje vacío"
    })
    response = client.post("/api/v1/telegram/signals", json={
        "channel": "@test", "message_id": "1", "text": "",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_ingest_signal_returns_success_for_valid_message(client, monkeypatch):
    monkeypatch.setattr(tapi, "process_telegram_signal", lambda *a, **kw: {
        "status": "success", "signal_id": "tg-xyz",
        "match_id": 99, "pick_id": 7,
        "analysis": {"tipster_odds": 1.95, "betano_current_odds": 2.10},
    })
    response = client.post("/api/v1/telegram/signals", json={
        "channel": "@tipster", "message_id": "42",
        "text": "Manchester United vs Chelsea cuota 1.95",
        "tipster": "TipsterTest",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["match_id"] == 99


def test_ingest_signal_returns_already_processed(client, monkeypatch):
    monkeypatch.setattr(tapi, "process_telegram_signal", lambda *a, **kw: {
        "status": "already_processed", "signal_id": "tg-dup",
        "channel": "@ch", "message_id": "1",
    })
    response = client.post("/api/v1/telegram/signals", json={
        "channel": "@ch", "message_id": "1",
        "text": "Barcelona vs PSG cuota 2.10",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "already_processed"


def test_ingest_signal_400_on_value_error(client, monkeypatch):
    def _raises(*a, **kw):
        raise ValueError("campo requerido faltante")

    monkeypatch.setattr(tapi, "process_telegram_signal", _raises)
    response = client.post("/api/v1/telegram/signals", json={
        "channel": "@ch", "message_id": "2", "text": "some text",
    })
    assert response.status_code == 400
    assert "campo requerido" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/v1/telegram/signals
# ---------------------------------------------------------------------------

def test_list_signals_returns_empty_on_fresh_db(client, isolated_db):
    response = client.get("/api/v1/telegram/signals?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["signals"] == []


def test_list_signals_with_data(client, isolated_db):
    from datetime import datetime, timezone
    isolated_db.execute(
        """INSERT INTO telegram_signals(
               signal_id,channel,message_id,tipster,raw_text,home_team,away_team,
               competition,market,selection,tipster_odds,matched_event_id,
               match_status,confidence,stake,analysis_result,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("s1", "@ch", "m1", "T", "Barcelona vs PSG cuota 2.10",
         "Barcelona", "PSG", "la liga", "1x2_ft", "home", 2.10, None,
         "pending_match", 0.7, 1.0, "{}", datetime.now(timezone.utc).isoformat()),
    )
    isolated_db.commit()

    response = client.get("/api/v1/telegram/signals?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["signals"][0]["channel"] == "@ch"


def test_list_signals_limit_capped_at_200(client, isolated_db):
    response = client.get("/api/v1/telegram/signals?limit=9999")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/telegram/retry-pending
# ---------------------------------------------------------------------------

def test_retry_pending_returns_summary(client, monkeypatch):
    monkeypatch.setattr(tapi, "retry_pending_matches", lambda: {
        "resolved": 2, "still_pending": 1, "total": 3
    })
    response = client.post("/api/v1/telegram/retry-pending")
    assert response.status_code == 200
    body = response.json()
    assert body["resolved"] == 2
    assert body["still_pending"] == 1
    assert body["total"] == 3


def test_retry_pending_returns_500_on_exception(client, monkeypatch):
    monkeypatch.setattr(tapi, "retry_pending_matches", lambda: (_ for _ in ()).throw(RuntimeError("DB locked")))
    response = client.post("/api/v1/telegram/retry-pending")
    assert response.status_code == 500
    assert "DB locked" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/v1/telegram/backtest
# ---------------------------------------------------------------------------

def test_telegram_backtest_endpoint_returns_engine_field(client, monkeypatch):
    monkeypatch.setattr(tapi, "evaluate_telegram_backtest", lambda **kw: {
        "source": "telegram",
        "engine": "betano_analyzer.backtest.evaluate",
        "bets": 0, "wins": 0, "losses": 0, "roi": 0.0,
    })
    response = client.get("/api/v1/telegram/backtest")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "betano_analyzer.backtest.evaluate"


def test_telegram_backtest_accepts_tipster_and_channel(client, monkeypatch):
    captured: dict = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return {"source": "telegram", "engine": "x", "bets": 0, "wins": 0,
                "losses": 0, "pushes": 0, "roi": 0.0, "hit_rate": 0.0}

    monkeypatch.setattr(tapi, "evaluate_telegram_backtest", _fake)
    client.get("/api/v1/telegram/backtest?tipster=TipsterX&channel=%40ch")
    assert captured.get("tipster") == "TipsterX"
    assert captured.get("channel") == "@ch"
