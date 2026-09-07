from betano_analyzer.backtest_report import build_backtest_report
from betano_analyzer.db import connect, initialize


def test_backtest_separates_original_and_conservative(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute("INSERT INTO matches(external_id,competition,home_team,away_team,kickoff) VALUES(?,?,?,?,?)", ("bt-1", "Premier League", "A", "B", "2026-09-07T20:00:00+00:00"))
        match_id = db.execute("SELECT id FROM matches WHERE external_id='bt-1'").fetchone()[0]
        db.execute("INSERT INTO picks(match_id,original_market,original_selection,original_odds,conservative_market,conservative_selection,conservative_odds,created_at) VALUES(?,?,?,?,?,?,?,?)", (match_id, "goals", "Over 2.5", 1.60, "goals", "Over 2", 1.40, "2026-09-07T10:00:00+00:00"))
        pick_id = db.execute("SELECT id FROM picks WHERE match_id=?", (match_id,)).fetchone()[0]
        settled = "2026-09-07T22:00:00+00:00"
        db.execute("INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds) VALUES(?,?,?,?,?)", (pick_id, "original", "lost", settled, 1.60))
        db.execute("INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds) VALUES(?,?,?,?,?)", (pick_id, "conservative", "won", settled, 1.40))
        db.commit()

    import os
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        report = build_backtest_report()
    finally:
        os.chdir(old)

    assert report["overall"]["original"]["losses"] == 1
    assert report["overall"]["conservative"]["wins"] == 1
    assert report["coverage"]["paired_picks"] == 1
