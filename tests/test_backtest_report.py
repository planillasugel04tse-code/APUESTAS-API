"""Tests for backtest_report: strategy separation, look-ahead bias prevention, ROI."""
from betano_analyzer.backtest import BacktestRow, evaluate, compare_strategies
from betano_analyzer.backtest_report import build_backtest_report
from betano_analyzer.db import connect, initialize
from betano_analyzer.dashboard import Period


# ---------------------------------------------------------------------------
# Existing test (preserved)
# ---------------------------------------------------------------------------

def test_backtest_separates_original_and_conservative(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff) VALUES(?,?,?,?,?)",
            ("bt-1", "Premier League", "A", "B", "2026-09-07T20:00:00+00:00"),
        )
        match_id = db.execute("SELECT id FROM matches WHERE external_id='bt-1'").fetchone()[0]
        db.execute(
            "INSERT INTO picks(match_id,original_market,original_selection,original_odds,"
            "conservative_market,conservative_selection,conservative_odds,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (match_id, "goals", "Over 2.5", 1.60, "goals", "Over 2", 1.40, "2026-09-07T10:00:00+00:00"),
        )
        pick_id = db.execute("SELECT id FROM picks WHERE match_id=?", (match_id,)).fetchone()[0]
        settled = "2026-09-07T22:00:00+00:00"
        db.execute(
            "INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds) VALUES(?,?,?,?,?)",
            (pick_id, "original", "lost", settled, 1.60),
        )
        db.execute(
            "INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds) VALUES(?,?,?,?,?)",
            (pick_id, "conservative", "won", settled, 1.40),
        )
        db.execute(
            "INSERT INTO bets(match_id,pick_id,selection,odds,stake,result,placed_at,settled_at) VALUES(?,?,?,?,?,?,?,?)",
            (match_id, pick_id, "Over 2", 1.40, 10, "won", "2026-09-07T10:00:00+00:00", settled),
        )
        db.commit()

    report = build_backtest_report(db_path=db_path)

    assert report["overall"]["original"]["losses"] == 1
    assert report["overall"]["conservative"]["wins"] == 1
    assert report["overall"]["actual"]["wins"] == 1
    assert report["overall"]["actual"]["stake"] == 10
    assert report["coverage"]["paired_picks"] == 1
    assert report["coverage"]["actual_bets"] == 1


# ---------------------------------------------------------------------------
# Core evaluate() tests
# ---------------------------------------------------------------------------

def test_backtest_evaluate_basic_roi():
    rows = [
        BacktestRow(result="won", odds=2.0, stake=1.0),
        BacktestRow(result="lost", odds=2.0, stake=1.0),
    ]
    result = evaluate(rows)
    assert result["bets"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["roi"] == 0.0  # break-even: +1 -1 = 0 on stake of 2
    assert result["hit_rate"] == 0.5


def test_backtest_evaluate_empty_returns_zeros():
    result = evaluate([])
    assert result["bets"] == 0
    assert result["roi"] == 0.0


def test_backtest_evaluate_rejects_invalid_odds():
    """Rows with odds <= 1 or non-settled results must be filtered out."""
    rows = [
        BacktestRow(result="pending", odds=2.0, stake=1.0),  # not settled
        BacktestRow(result="won", odds=1.0, stake=1.0),       # odds <= 1
        BacktestRow(result="won", odds=2.0, stake=1.0),       # valid
    ]
    result = evaluate(rows)
    assert result["bets"] == 1
    assert result["wins"] == 1


def test_backtest_compare_strategies():
    original = [BacktestRow("won", 2.0, 1.0), BacktestRow("lost", 2.0, 1.0)]
    conservative = [BacktestRow("won", 1.5, 1.0), BacktestRow("won", 1.5, 1.0)]
    result = compare_strategies(original, conservative)
    assert result["original"]["roi"] == 0.0
    assert result["conservative"]["roi"] > 0


# ---------------------------------------------------------------------------
# Look-ahead bias prevention test
# ---------------------------------------------------------------------------

def test_backtest_period_filter_excludes_future_results(tmp_path):
    """The period filter must exclude results settled AFTER the period end date.

    This prevents look-ahead bias: results that were not yet known at the
    end of the analysis window must not appear in the backtest report.
    """
    db_path = tmp_path / "lookahead.sqlite3"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff) VALUES(?,?,?,?,?)",
            ("la-1", "La Liga", "X", "Y", "2026-08-01T20:00:00+00:00"),
        )
        match_id = db.execute("SELECT id FROM matches WHERE external_id='la-1'").fetchone()[0]
        db.execute(
            "INSERT INTO picks(match_id,original_market,original_selection,original_odds,created_at) VALUES(?,?,?,?,?)",
            (match_id, "1x2", "home", 2.00, "2026-08-01T10:00:00+00:00"),
        )
        pick_id = db.execute("SELECT id FROM picks WHERE match_id=?", (match_id,)).fetchone()[0]
        # Settled AFTER the 'today' reference period would cover
        db.execute(
            "INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds) VALUES(?,?,?,?,?)",
            (pick_id, "original", "won", "2029-12-31T23:00:00+00:00", 2.00),
        )
        db.commit()

    # HOY period — the far-future settle date must NOT appear
    report = build_backtest_report(Period.HOY, db_path=db_path)
    assert report["overall"]["original"]["bets"] == 0, (
        "Future-settled result leaked into a past period — look-ahead bias detected!"
    )


def test_backtest_push_not_counted_as_win_or_loss(tmp_path):
    """Push results must be counted separately, not forced into win/loss."""
    db_path = tmp_path / "push.sqlite3"
    initialize(db_path)
    with connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff) VALUES(?,?,?,?,?)",
            ("push-1", "Serie A", "P", "Q", "2026-09-01T20:00:00+00:00"),
        )
        match_id = db.execute("SELECT id FROM matches WHERE external_id='push-1'").fetchone()[0]
        db.execute(
            "INSERT INTO picks(match_id,original_market,original_selection,original_odds,created_at) VALUES(?,?,?,?,?)",
            (match_id, "goals", "over 2.5", 1.90, "2026-09-01T10:00:00+00:00"),
        )
        pick_id = db.execute("SELECT id FROM picks WHERE match_id=?", (match_id,)).fetchone()[0]
        db.execute(
            "INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds) VALUES(?,?,?,?,?)",
            (pick_id, "original", "push", "2026-09-01T22:00:00+00:00", 1.90),
        )
        db.commit()

    report = build_backtest_report(db_path=db_path)
    assert report["overall"]["original"]["wins"] == 0
    assert report["overall"]["original"]["losses"] == 0
    assert report["overall"]["original"]["pushes"] == 1
