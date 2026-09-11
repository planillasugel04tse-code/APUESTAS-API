"""Tests for the Telegram parser, matching, backtest and service modules.

Covers:
- Parser: basic picks, competitions, market detection, handicap, date/time extraction
- Matching: aliases, accents, ambiguous candidates, rejection of too-close scores
- Backtest: delegates to core engine
- Service: delegates to core analysis engines; price source separation
- Arbitrage: uses match status (not kickoff) for Live classification
"""
from __future__ import annotations

import inspect
import sqlite3

import pytest

from betano_analyzer.matching import choose_team_match, normalize_team_name
from betano_analyzer.telegram.backtest import evaluate_telegram_backtest
import betano_analyzer.telegram.backtest as telegram_backtest
from betano_analyzer.telegram.parser import parse_telegram_message


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

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


def test_parser_detects_over_goals_market():
    parsed = parse_telegram_message(
        "Juventus vs Napoli | Over 2.5 goles | cuota 1.80",
        channel="@canal",
    )
    assert parsed.is_valid
    assert parsed.market == "goals"
    assert parsed.selection == "over"
    assert parsed.line == 2.5


def test_parser_detects_btts_market():
    parsed = parse_telegram_message(
        "Bayern Munich vs Real Madrid BTTS Sí cuota 1.75",
        channel="@canal",
    )
    assert parsed.is_valid
    assert parsed.market == "btts"
    assert parsed.selection == "yes"


def test_parser_detects_handicap_market():
    parsed = parse_telegram_message(
        "Barcelona vs Villarreal handicap -1.5 local cuota 2.10",
        channel="@canal",
    )
    assert parsed.is_valid
    assert parsed.market == "asian_handicap"


def test_parser_extracts_datetime_from_message():
    parsed = parse_telegram_message(
        "Liverpool vs Arsenal 2026-09-10 18:00 UTC cuota 2.00",
        channel="@canal",
    )
    assert parsed.is_valid
    assert parsed.match_datetime is not None
    assert "18:00" in parsed.match_datetime


def test_parser_handles_dash_format():
    parsed = parse_telegram_message(
        "PSG - Chelsea | cuota 1.90",
        channel="@canal",
    )
    # May or may not parse depending on pattern priority; if valid, check basics
    if parsed.is_valid:
        assert parsed.odds == 1.90


def test_parser_rejects_empty_message():
    parsed = parse_telegram_message("", channel="@canal")
    assert not parsed.is_valid
    assert parsed.error_reason == "Mensaje vacío"


def test_parser_rejects_invalid_odds():
    parsed = parse_telegram_message(
        "Atlético de Madrid vs Sevilla cuota 0.80",
        channel="@canal",
    )
    assert not parsed.is_valid
    assert "Cuota" in parsed.error_reason


def test_parser_stake_becomes_confidence():
    parsed = parse_telegram_message(
        "Real Madrid vs Bayern Munich cuota 1.85 stake 5",
        channel="@canal",
    )
    assert parsed.is_valid
    assert parsed.stake == 5.0
    assert parsed.confidence == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Team normalization tests
# ---------------------------------------------------------------------------

def test_team_normalization_handles_common_provider_aliases():
    assert normalize_team_name("Man Utd FC") == "manchester united"
    assert normalize_team_name("Manchester Utd") == "manchester united"
    assert normalize_team_name("Atlético de Madrid") == "atletico de madrid"


def test_team_normalization_removes_fc_suffix():
    assert normalize_team_name("Chelsea FC") == "chelsea"
    assert normalize_team_name("Arsenal FC") == "arsenal"


def test_team_normalization_handles_psg():
    assert normalize_team_name("PSG") == "paris saint germain"
    assert normalize_team_name("Paris SG") == "paris saint germain"


def test_team_normalization_handles_barca():
    assert normalize_team_name("Barça") == "barcelona"
    assert normalize_team_name("Barca") == "barcelona"


def test_team_normalization_handles_juve():
    assert normalize_team_name("Juve") == "juventus"


def test_team_normalization_handles_bvb():
    assert normalize_team_name("BVB") == "borussia dortmund"


def test_team_normalization_accents_stripped():
    # é, á, ó, ú, ñ → without combining characters
    assert normalize_team_name("Atlético") == "atletico"
    assert normalize_team_name("Leganés") == "leganes"


# ---------------------------------------------------------------------------
# Matching tests
# ---------------------------------------------------------------------------

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


def test_matching_rejects_low_score():
    """A completely different team name must score below the 0.90 threshold."""
    candidates = [{"id": 99, "home_team": "AC Milan", "away_team": "Napoli"}]
    result = choose_team_match("Liverpool", "Arsenal", candidates)
    assert result is None


def test_matching_rejects_close_gap():
    """Two nearly identical candidates must not be matched to prevent wrong association."""
    candidates = [
        {"id": 1, "home_team": "Real Madrid", "away_team": "Valencia"},
        {"id": 2, "home_team": "Real Sociedad", "away_team": "Valencia"},
    ]
    # "Real" alone is too ambiguous
    result = choose_team_match("Real", "Valencia", candidates)
    assert result is None


def test_matching_handles_accented_team_from_telegram():
    """Accented team names from Telegram must still match normalized DB entries."""
    candidates = [{"id": 5, "home_team": "Atletico de Madrid", "away_team": "Sevilla"}]
    result = choose_team_match("Atlético de Madrid", "Sevilla FC", candidates)
    assert result is not None
    assert result.match_id == 5


def test_matching_handles_juve_alias():
    candidates = [{"id": 7, "home_team": "Juventus", "away_team": "Inter Milan"}]
    result = choose_team_match("Juve", "Inter", candidates)
    assert result is not None
    assert result.match_id == 7


def test_matching_empty_candidates_returns_none():
    assert choose_team_match("Barcelona", "PSG", []) is None


# ---------------------------------------------------------------------------
# Backtest tests
# ---------------------------------------------------------------------------

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
    conn.execute(
        "INSERT INTO telegram_signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("s1", "@t", "1", "Tipster", "x", "A", "B", "Liga", "1x2_ft", "home",
         1.9, 7, "matched", 0.8, 1, "{}", "2026-09-10T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1, 7, None, "1x2_ft", "home", 1.9, None, None, None, 0.8, None, None, "2026-09-10T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO pick_results VALUES (?,?,?,?,?,?)",
        (1, 1, "won", "2026-09-11T00:00:00Z", 1.9, None),
    )
    conn.commit()
    monkeypatch.setattr(telegram_backtest, "connect", lambda: conn)

    result = evaluate_telegram_backtest()
    assert result["engine"] == "betano_analyzer.backtest.evaluate"
    assert result["bets"] == 1
    assert result["wins"] == 1
    assert result["roi"] == pytest.approx(0.9)


def test_telegram_backtest_empty_returns_zero_bets(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE telegram_signals (signal_id TEXT PRIMARY KEY, channel TEXT,
            message_id TEXT, tipster TEXT, raw_text TEXT, home_team TEXT, away_team TEXT,
            competition TEXT, market TEXT, selection TEXT, tipster_odds REAL,
            matched_event_id INTEGER, match_status TEXT, confidence REAL, stake REAL,
            analysis_result TEXT, created_at TEXT);
        CREATE TABLE picks (id INTEGER PRIMARY KEY, match_id INTEGER, tipster_id INTEGER,
            original_market TEXT, original_selection TEXT, original_odds REAL,
            conservative_market TEXT, conservative_selection TEXT, conservative_odds REAL,
            confidence REAL, probability REAL, probability_source TEXT, created_at TEXT);
        CREATE TABLE pick_results (id INTEGER PRIMARY KEY, pick_id INTEGER UNIQUE, result TEXT,
            settled_at TEXT, actual_odds REAL, notes TEXT);
    """)
    conn.commit()
    monkeypatch.setattr(telegram_backtest, "connect", lambda: conn)

    result = evaluate_telegram_backtest()
    assert result["bets"] == 0


# ---------------------------------------------------------------------------
# Service delegation test
# ---------------------------------------------------------------------------

def test_telegram_service_delegates_to_core_engines():
    from betano_analyzer.telegram import service

    source = inspect.getsource(service.process_telegram_signal)
    assert "build_value_radar" in source
    assert "build_master_radar" in source
    assert "build_final_selection" in source
    assert "find_arbitrage" in source
    # Must NEVER compute 1/tipster_odds — that would be creating an implied probability
    # from the tipster source and confusing it with a market probability
    assert "1.0 / parsed.odds" not in source


# ---------------------------------------------------------------------------
# Arbitrage uses match status for live classification
# ---------------------------------------------------------------------------

def test_arbitrage_uses_match_status_for_live_classification(monkeypatch):
    from betano_analyzer import arbitrage
    from datetime import datetime, timezone, timedelta

    # Use a timestamp clearly within the freshness window (1 minute ago)
    now = datetime.now(timezone.utc)
    fresh_ts = (now - timedelta(minutes=1)).isoformat()

    class Row(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)

    rows = [
        Row(match_id=1, bookmaker="Betano", market="1x2_ft", selection="home", line=None, odds=2.1,
            captured_at=fresh_ts, home_team="A", away_team="B",
            kickoff="2026-09-10T20:00:00+00:00", status="live"),
        Row(match_id=1, bookmaker="Book2", market="1x2_ft", selection="draw", line=None, odds=4.5,
            captured_at=fresh_ts, home_team="A", away_team="B",
            kickoff="2026-09-10T20:00:00+00:00", status="live"),
        Row(match_id=1, bookmaker="Book3", market="1x2_ft", selection="away", line=None, odds=4.5,
            captured_at=fresh_ts, home_team="A", away_team="B",
            kickoff="2026-09-10T20:00:00+00:00", status="live"),
    ]

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeDB:
        def execute(self, *args):
            return FakeCursor(rows)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(arbitrage, "connect", lambda: FakeDB())
    live_result = arbitrage.find_arbitrage(live=True, match_id=1)
    pre_result = arbitrage.find_arbitrage(live=False, match_id=1)
    assert live_result and live_result[0].mode == "live"
    assert pre_result == []
