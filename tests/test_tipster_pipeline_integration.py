from __future__ import annotations

from datetime import datetime, timezone

from betano_analyzer.db import connect, initialize
from betano_analyzer.tipster_intelligence import StatisticalEvidence, TipsterPick
from betano_analyzer.tipster_pipeline import enrich_tipster_pick


def test_conservative_goal_quote_uses_transformed_line(tmp_path, monkeypatch):
    db_path = tmp_path / "pipeline.sqlite3"
    initialize(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    now = datetime.now(timezone.utc).isoformat()

    with connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            ("m1", "Liga 1", "A", "B", now, "scheduled"),
        )
        match_id = db.execute("SELECT id FROM matches WHERE external_id='m1'").fetchone()[0]
        # Original pick is Over 2.5; conservative market is Over 1.5.
        db.execute(
            "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
            (match_id, "Book Original", "goals", "Over 2.5", 1.75, now, 2.5),
        )
        db.execute(
            "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
            (match_id, "Book Safer", "goals", "Over 1.5", 1.55, now, 1.5),
        )
        db.execute(
            "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
            (match_id, "betano.pe", "goals", "Over 2.5", 1.80, now, 2.5),
        )
        db.commit()

    pick = TipsterPick(
        source="test",
        source_type="telegram",
        event="A vs B",
        market="goals",
        selection="Over 2.5",
        odds=1.75,
        line=2.5,
    )
    result = enrich_tipster_pick(match_id, pick, StatisticalEvidence(), max_age_minutes=10)

    assert result.market.original is not None
    assert result.market.original.line == 2.5
    assert result.market.safer is not None
    assert result.market.safer.line == 1.5
    assert result.market.safer.odds == 1.55
    assert result.market.peru
    assert result.market.peru[0].bookmaker == "betano.pe"
    assert result.market.peru[0].odds == 1.80
