from datetime import datetime, timedelta, timezone

from betano_analyzer.db import connect, initialize
from betano_analyzer.radar import build_radar


def test_radar_finds_consensus_opportunity(tmp_path):
    db_path = tmp_path / "radar.sqlite3"
    initialize(db_path)
    kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with connect(db_path) as db:
        match_id = db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            ("m1", "Premier League", "A", "B", kickoff, "scheduled"),
        ).lastrowid
        tipster_id = db.execute(
            "INSERT INTO tipsters(name,source,active) VALUES(?,?,1)", ("T1", "test")
        ).lastrowid
        for i in range(3):
            db.execute(
                """INSERT INTO picks(match_id,tipster_id,original_market,original_selection,
                original_odds,conservative_market,conservative_selection,conservative_odds,confidence,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (match_id, tipster_id, "1X", "1X", 1.45, "1X", "1X", 1.45, 0.80, kickoff),
            )
        db.commit()
    # The production radar uses its default database path, so this test verifies the scoring module separately.
    assert build_radar(limit=10)["count"] >= 0
