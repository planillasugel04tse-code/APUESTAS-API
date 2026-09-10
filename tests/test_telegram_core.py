from __future__ import annotations

import inspect
import sqlite3

import pytest

from betano_analyzer.matching import choose_team_match, normalize_team_name
from betano_analyzer.telegram.backtest import evaluate_telegram_backtest
from betano_analyzer.telegram.parser import parse_telegram_message
import betano_analyzer.telegram.backtest as telegram_backtest


def test_telegram_parser_preserves_published_odds():
    parsed = parse_telegram_message(
        "🏆UEFA Champions League ⚽ Manchester United vs Sabah Baku 💰1.62 💵200€",
        channel="@tipster",
    )
    assert parsed.is_valid
    assert parsed.home_team == "Manchester United"
    assert parsed.away_team == "Sabah Baku"
    assert parsed.competition == "uefa champions league"
    assert parsed.odds == 1.62
    assert parsed.market == "1x2"
    assert parsed.selection == "home"


def test_team_normalization_handles_common_provider_aliases():
    assert normalize_team_name("Man Utd FC") == "man united"
    assert normalize_team_name("Atlético de Madrid") == "atletico de madrid"


def test_team_matching_accepts_safe_alias_and_rejects_ambiguous_candidate():
    candidates = [
        {"id": 10, "home_team": "Manchester United", "away_team": "Sabah Baku"},
        {"id": 11, "home_team": "Manchester City", "away_team": "Sabah Baku"},
    ]
    selected = choose_team_match("Man Utd", "Sabah Baku", candidates)
    assert selected is not None
    assert selected.match_id == 10

    ambiguous = [
        {"id": 20, "home_team": "United", "away_team": "City"},
        {"id": 21, "home_team": "United", "away_team": "City"},
    ]
    assert choose_team_match("United", "City", ambiguous) is None


def test_telegram_backtest_uses_core_evaluate_engine(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE telegram_signals (
            signal_id TEXT PRIMARY KEY, channel TEXT, message_id TEXT, tipster TEXT,
            raw_text TEXT, home_team TEXT, away_team TEXT, competition TEXT,
            market TEXT, selection TEXT, tipster_odds REAL, matched_event_id INTEGER,
            match_status TEXT, confidence REAL, stake REAL, analysis_result TEXT, created_at TEXT
        );
        CREATE TABLE picks (
            id INTEGER PRIMARY KEY, match_id INTEGER, tipster_id INTEGER,
            original_market TEXT, original_selection TEXT, original_odds REAL,
            conservative_market TEXT, conservative_selection TEXT, conservative_odds REAL,
            confidence REAL, probability REAL, probability_source TEXT, created_at TEXT
        );
        CREATE TABLE pick_results (
            id INTEGER PRIMARY KEY, pick_id INTEGER UNIQUE, result TEXT,
            settled_at TEXT, actual_odds REAL, notes TEXT
        );
    """)
    conn.execute("INSERT INTO telegram_signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("s1", "@t", "1", "Tipster", "x", "A", "B", "Liga", "1x2_ft", "home", 1.9, 7, "matched", 0.8, 1, "{}", "2026-09-10T00:00:00Z"))
    conn.execute("INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (1, 7, None, "1x2_ft", "home", 1.9, None, None, None, 0.8, None, None, "2026-09-10T00:00:00Z"))
    conn.execute("INSERT INTO pick_results VALUES (?,?,?,?,?,?)", (1, 1, "won", "2026-09-11T00:00:00Z", 1.9, None))
    conn.commit()
    monkeypatch.setattr(telegram_backtest, "connect", lambda: conn)

    result = evaluate_telegram_backtest()
    assert result["engine"] == "betano_analyzer.backtest.evaluate"
    assert result["bets"] == 1
    assert result["wins"] == 1
    assert result["roi"] == pytest.approx(0.9)


def test_telegram_service_delegates_to_core_engines():
    from betano_analyzer.telegram import service
    source = inspect.getsource(service.process_telegram_signal)
    assert "build_value_radar" in source
    assert "build_master_radar" in source
    assert "build_final_selection" in source
    assert "find_arbitrage" in source
    assert "1.0 / parsed.odds" not in source
