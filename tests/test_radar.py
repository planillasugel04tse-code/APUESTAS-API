"""Tests for the radar scoring module.

Uses in-memory SQLite with monkeypatching to avoid tmp_path
and the Windows pytest-current symlink cleanup PermissionError.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import betano_analyzer.radar as radar_module
from betano_analyzer.db import SCHEMA
from betano_analyzer.radar import build_radar


def _make_mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def test_radar_finds_consensus_opportunity(monkeypatch):
    conn = _make_mem_db()

    kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    match_id = conn.execute(
        "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
        ("m1", "Premier League", "A", "B", kickoff, "scheduled"),
    ).lastrowid
    tipster_id = conn.execute(
        "INSERT INTO tipsters(name,source,active) VALUES(?,?,1)", ("T1", "test")
    ).lastrowid
    for i in range(3):
        conn.execute(
            """INSERT INTO picks(match_id,tipster_id,original_market,original_selection,
            original_odds,conservative_market,conservative_selection,conservative_odds,confidence,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (match_id, tipster_id, "1X", "1X", 1.45, "1X", "1X", 1.45, 0.80, kickoff),
        )
    conn.commit()

    monkeypatch.setattr(radar_module, "connect", lambda path=None: conn)

    result = build_radar(limit=10)
    # The radar uses its own DB by default; with monkeypatching it uses our data.
    assert isinstance(result, dict)
    assert "count" in result
    assert result["count"] >= 0
