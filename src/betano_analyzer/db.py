from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, competition TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL, kickoff TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled');
CREATE TABLE IF NOT EXISTS tipsters (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, source TEXT, country TEXT, language TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS picks (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL REFERENCES matches(id), tipster_id INTEGER REFERENCES tipsters(id), original_market TEXT NOT NULL, original_selection TEXT NOT NULL, original_odds REAL, conservative_market TEXT, conservative_selection TEXT, conservative_odds REAL, confidence REAL, probability REAL, probability_source TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS odds (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL REFERENCES matches(id), bookmaker TEXT NOT NULL, market TEXT NOT NULL, selection TEXT NOT NULL, odds REAL NOT NULL, captured_at TEXT NOT NULL, line REAL);
CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL REFERENCES matches(id), pick_id INTEGER REFERENCES picks(id), selection TEXT NOT NULL, odds REAL NOT NULL, stake REAL NOT NULL, result TEXT NOT NULL DEFAULT 'pending', cashout REAL, placed_at TEXT NOT NULL, settled_at TEXT);
CREATE TABLE IF NOT EXISTS source_configs (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, base_url TEXT, enabled INTEGER NOT NULL DEFAULT 0, notes TEXT);
CREATE TABLE IF NOT EXISTS pick_results (id INTEGER PRIMARY KEY AUTOINCREMENT, pick_id INTEGER NOT NULL UNIQUE REFERENCES picks(id), result TEXT NOT NULL, settled_at TEXT NOT NULL, actual_odds REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS pick_strategy_results (id INTEGER PRIMARY KEY AUTOINCREMENT, pick_id INTEGER NOT NULL REFERENCES picks(id), strategy TEXT NOT NULL, result TEXT NOT NULL, settled_at TEXT NOT NULL, actual_odds REAL, notes TEXT, UNIQUE(pick_id, strategy));
CREATE TABLE IF NOT EXISTS clv_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL REFERENCES matches(id), bookmaker TEXT NOT NULL, market TEXT NOT NULL, selection TEXT NOT NULL, line REAL, entry_odds REAL NOT NULL, closing_odds REAL NOT NULL, clv REAL NOT NULL, captured_at TEXT NOT NULL, UNIQUE(match_id, bookmaker, market, selection, line));

CREATE TABLE IF NOT EXISTS telegram_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    message_id TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    status TEXT NOT NULL,
    pick_id INTEGER,
    parsed_data TEXT,
    received_at TEXT NOT NULL,
    UNIQUE(channel, message_id)
);
CREATE TABLE IF NOT EXISTS telegram_signals (
    signal_id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    message_id TEXT NOT NULL,
    tipster TEXT,
    raw_text TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    competition TEXT,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    tipster_odds REAL,
    matched_event_id INTEGER,
    match_status TEXT NOT NULL,
    confidence REAL,
    stake REAL,
    analysis_result TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(matched_event_id) REFERENCES matches(id),
    UNIQUE(channel, message_id)
);
"""

MIGRATIONS = (
    "ALTER TABLE picks ADD COLUMN probability REAL",
    "ALTER TABLE picks ADD COLUMN probability_source TEXT",
    "ALTER TABLE odds ADD COLUMN line REAL",
)


def connect(path: str | Path = "betano_analyzer.sqlite3") -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: str | Path = "betano_analyzer.sqlite3") -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        for statement in MIGRATIONS:
            try:
                connection.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        connection.commit()
