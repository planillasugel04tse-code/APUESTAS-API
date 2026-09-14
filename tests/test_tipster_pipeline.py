from __future__ import annotations

from datetime import datetime, timezone

from betano_analyzer.db import initialize, connect
from betano_analyzer.tipster_intelligence import StatisticalEvidence, TipsterPick
from betano_analyzer.tipster_pipeline import enrich_tipster_pick


def _seed(tmp_path):
    db_path = tmp_path / "pipeline.sqlite3"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id, competition, home_team, away_team, kickoff, status) VALUES(?,?,?,?,?,?)",
            ("m1", "Liga", "Local", "Visitante", "2026-09-14T20:00:00+00:00", "scheduled"),
        )
        match_id = db.execute("SELECT id FROM matches").fetchone()[0]
        now = datetime.now(timezone.utc).isoformat()
        db.executemany(
            "INSERT INTO odds(match_id, bookmaker, market, selection, odds, captured_at, line) VALUES(?,?,?,?,?,?,?)",
            [
                (match_id, "Betano", "1x2", "Local", 2.10, now, None),
                (match_id, "Apuesta Total", "1x2", "Local", 2.00, now, None),
                (match_id, "Betano", "double chance", "1X", 1.52, now, None),
            ],
        )
        history = []
        for index in range(5):
            history.append(("Local", f"Rival-{index}", 2, 0 if index < 4 else 1, 1, f"2026-09-{10-index:02d}", f"local-{index}", "fixture"))
            history.append(("Visitante", f"RivalV-{index}", 1 if index < 3 else 0, 0 if index < 3 else 1, 0, f"2026-09-{10-index:02d}", f"away-{index}", "fixture"))
        db.executemany(
            "INSERT INTO team_match_history(team, opponent, goals_for, goals_against, is_home, played_at, external_match_id, source, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [(team, opponent, gf, ga, home, played, external, source, now) for team, opponent, gf, ga, home, played, external, source in history],
        )
        db.commit()
    return db_path, match_id


def test_enrichment_uses_best_fresh_original_and_safer_quote(tmp_path, monkeypatch):
    db_path, match_id = _seed(tmp_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    pick = TipsterPick(
        source="tipster-x",
        source_type="tipster",
        event="Local vs Visitante",
        market="1x2",
        selection="Local",
        odds=1.80,
    )
    result = enrich_tipster_pick(
        match_id,
        pick,
        StatisticalEvidence(model_probability=0.58, data_completeness=0.8),
    )
    assert result.market.original is not None
    assert result.market.original.bookmaker == "Betano"
    assert result.market.original.odds == 2.10
    assert result.market.safer is not None
    assert result.market.safer.odds == 1.52
    assert result.analysis.offered_odds == 2.10
    assert result.analysis.safer.safer_odds == 1.52
    assert result.statistics.status == "OK"
    assert result.statistics.sample_size == 5
    assert result.statistics.data_completeness == 1.0


def test_enrichment_falls_back_to_stored_statistics_when_model_probability_is_missing(tmp_path, monkeypatch):
    db_path, match_id = _seed(tmp_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    pick = TipsterPick(
        source="tipster-y",
        source_type="tipster",
        event="Local vs Visitante",
        market="1x2",
        selection="Local",
    )
    result = enrich_tipster_pick(match_id, pick, StatisticalEvidence())
    assert result.statistics.status == "OK"
    assert result.statistics.selection_probability is not None
    assert result.analysis.probability == result.statistics.selection_probability
    assert result.analysis.evidence.data_completeness == 1.0
    assert result.analysis.evidence.sample_size == 5
