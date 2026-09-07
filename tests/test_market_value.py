from betano_analyzer.market_value import scan_market


def test_scan_market_removes_margin_and_calculates_ev():
    rows = [
        {"match_id": 1, "bookmaker": "Betano", "market": "1x2", "line": None, "selection": "home", "odds": 2.20},
        {"match_id": 1, "bookmaker": "Betano", "market": "1x2", "line": None, "selection": "draw", "odds": 3.40},
        {"match_id": 1, "bookmaker": "Betano", "market": "1x2", "line": None, "selection": "away", "odds": 3.20},
    ]
    values = scan_market(rows)
    assert len(values) == 3
    assert all(v.overround > 0 for v in values)
    home = next(v for v in values if v.selection == "home")
    assert home.fair_probability > 0
    assert home.fair_odds > 1
    assert abs(home.ev - (home.fair_probability * 2.20 - 1)) < 1e-9


def test_scan_market_keeps_lines_separate():
    rows = [
        {"match_id": 2, "bookmaker": "Betano", "market": "goals", "line": 2.5, "selection": "over", "odds": 1.90},
        {"match_id": 2, "bookmaker": "Betano", "market": "goals", "line": 2.5, "selection": "under", "odds": 1.90},
        {"match_id": 2, "bookmaker": "Betano", "market": "goals", "line": 3.5, "selection": "over", "odds": 2.40},
        {"match_id": 2, "bookmaker": "Betano", "market": "goals", "line": 3.5, "selection": "under", "odds": 1.55},
    ]
    values = scan_market(rows)
    assert {v.line for v in values} == {2.5, 3.5}
