from datetime import datetime, timedelta, timezone

from betano_analyzer.db import connect, initialize
from betano_analyzer.tipster_market import best_market_quote, best_market_quotes


def test_best_market_quote_prefers_highest_fresh_quote(tmp_path, monkeypatch):
    db_path = tmp_path / "quotes.sqlite3"
    initialize(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    captured = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as db:
        db.execute("INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)", ("m1", "Liga 1", "A", "B", captured, "scheduled"))
        match_id = db.execute("SELECT id FROM matches WHERE external_id='m1'").fetchone()[0]
        db.execute("INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)", (match_id, "Book A", "1X2", "Local", 1.70, captured, None))
        db.execute("INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)", (match_id, "Book B", "1X2", "Local", 1.85, captured, None))
        db.commit()

    quote = best_market_quote(match_id, "1X2", "Local", max_age_minutes=10)
    assert quote is not None
    assert quote["bookmaker"] == "Book B"
    assert quote["odds"] == 1.85


def test_best_market_quotes_drops_stale_and_wrong_line(tmp_path, monkeypatch):
    db_path = tmp_path / "quotes.sqlite3"
    initialize(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    fresh = datetime.now(timezone.utc).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    with connect(db_path) as db:
        db.execute("INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)", ("m2", "Liga 1", "A", "B", fresh, "scheduled"))
        match_id = db.execute("SELECT id FROM matches WHERE external_id='m2'").fetchone()[0]
        rows = [
            ("Fresh", 1.80, fresh, 1.5),
            ("Stale", 2.00, stale, 1.5),
            ("Wrong line", 2.20, fresh, 2.5),
        ]
        for bookmaker, odds, captured, line in rows:
            db.execute("INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)", (match_id, bookmaker, "Goals", "Over", odds, captured, line))
        db.commit()

    quotes = best_market_quotes(match_id, "Goals", "Over", line=1.5, max_age_minutes=60)
    assert [q.bookmaker for q in quotes] == ["Fresh"]
