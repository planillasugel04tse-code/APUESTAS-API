from betano_analyzer.odds_api_io import _market_rows


def test_market_rows_preserves_lines_and_bookmakers():
    payload = {
        "bookmakers": {
            "Betano": [
                {"name": "Totals", "updatedAt": "2026-09-07T10:00:00Z", "odds": [{"hdp": 2.5, "over": "1.80", "under": "2.00"}]},
                {"name": "ML", "updatedAt": "2026-09-07T10:00:00Z", "odds": [{"home": "1.50", "draw": "4.20", "away": "6.00"}]},
            ]
        }
    }
    rows = _market_rows("123", payload)
    totals = [row for row in rows if row.market == "Totals"]
    assert len(totals) == 2
    assert {row.line for row in totals} == {2.5}
    assert any(row.bookmaker == "Betano" and row.selection == "home" and row.odds == 1.5 for row in rows)
