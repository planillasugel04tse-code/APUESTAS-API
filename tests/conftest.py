"""Shared pytest fixtures for the betano-analyzer test suite.

Centralizes the in-memory SQLite database fixture so individual test modules
do not need to duplicate the setup logic.
"""
from __future__ import annotations

import sqlite3

import pytest

import betano_analyzer.db as db_module
import betano_analyzer.telegram.service as svc_module
import betano_analyzer.telegram.backtest as tg_backtest_module
import betano_analyzer.arbitrage as arb_module
import betano_analyzer.radar as radar_module
import betano_analyzer.radar_value as rv_module
import betano_analyzer.master_radar as mr_module
import betano_analyzer.final_selector as fs_module
import betano_analyzer.backtest_report as br_module


@pytest.fixture()
def mem_db(monkeypatch):
    """Fresh in-memory SQLite database with the full schema applied.

    All modules that call ``connect()`` are monkeypatched to use this
    shared connection, so tests never touch the filesystem DB and are
    fully isolated from each other.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(db_module.SCHEMA)
    conn.commit()

    def _connect(path=None):
        return conn

    monkeypatch.setattr(db_module, "connect", _connect)
    monkeypatch.setattr(svc_module, "connect", _connect)
    monkeypatch.setattr(tg_backtest_module, "connect", _connect)
    monkeypatch.setattr(arb_module, "connect", _connect)
    monkeypatch.setattr(radar_module, "connect", _connect)
    monkeypatch.setattr(rv_module, "connect", _connect)
    monkeypatch.setattr(mr_module, "connect", _connect)
    monkeypatch.setattr(br_module, "connect", _connect)

    return conn


@pytest.fixture()
def mem_db_no_analysis(monkeypatch, mem_db):
    """``mem_db`` plus stubs for the heavy analysis engines.

    Use this fixture when the test focuses on the Telegram ingestion pipeline
    and does not need real output from the radar/selector engines.
    """
    monkeypatch.setattr(rv_module, "build_value_radar", lambda **kw: {"opportunities": []})
    monkeypatch.setattr(mr_module, "build_master_radar", lambda **kw: {"opportunities": []})
    monkeypatch.setattr(fs_module, "build_final_selection", lambda **kw: {"opportunities": []})
    return mem_db
