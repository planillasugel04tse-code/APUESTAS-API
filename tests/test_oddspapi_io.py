from betano_analyzer.ingest import normalize_market
from betano_analyzer.oddspapi_io import parse_odds


def test_parse_oddspapi_betano_odds():
    payload = {
        "fixtureId": "id-demo",
        "updatedAt": "2026-09-07T15:00:00Z",
        "bookmakerOdds": {
            "betano.pe": {
                "bookmakerIsActive": True,
                "suspended": False,
                "markets": {
                    "101": {
                        "marketActive": True,
                        "outcomes": {
                            "101": {"players": {"0": {"active": True, "bookmakerOutcomeId": "home", "changedAt": "2026-09-07T15:00:00Z", "price": 2.10}}},
                            "102": {"players": {"0": {"active": True, "bookmakerOutcomeId": "draw", "price": 3.30}}},
                        },
                    },
                    "106": {
                        "marketActive": True,
                        "outcomes": {
                            "106": {"players": {"0": {"active": True, "bookmakerOutcomeId": "2.5/over", "price": 1.85}}}
                        },
                    },
                },
            }
        },
    }
    catalog = [
        {"marketId": 101, "marketName": "Full Time Result", "handicap": 0, "period": "fulltime", "marketType": "1x2", "outcomes": [{"outcomeId": 101, "outcomeName": "1"}, {"outcomeId": 102, "outcomeName": "X"}]},
        {"marketId": 106, "marketName": "Over Under Full Time 2.5", "handicap": 2.5, "period": "fulltime", "marketType": "totals", "outcomes": [{"outcomeId": 106, "outcomeName": "Over"}]},
    ]

    rows = parse_odds(payload, market_catalog=catalog)

    assert len(rows) == 3
    assert rows[0].bookmaker == "betano.pe"
    assert rows[0].market == "1x2_ft"
    assert rows[0].selection == "home"
    assert rows[0].odds == 2.10
    assert rows[1].selection == "draw"
    assert rows[2].market == "goals_ft"
    assert rows[2].selection == "over"
    assert rows[2].line == 2.5


def test_parse_oddspapi_uses_catalog_line_when_bookmaker_id_has_no_line():
    payload = {
        "fixtureId": "id-demo",
        "bookmakerOdds": {
            "betano.pe": {
                "suspended": False,
                "markets": {
                    "106": {
                        "marketActive": True,
                        "outcomes": {
                            "106": {"players": {"0": {"active": True, "bookmakerOutcomeId": "over", "price": 1.90}}}
                        },
                    }
                },
            }
        },
    }
    catalog = [{"marketId": 106, "marketName": "Over Under Full Time 2.5", "handicap": 2.5, "period": "fulltime", "marketType": "totals", "outcomes": [{"outcomeId": 106, "outcomeName": "Over"}]}]

    rows = parse_odds(payload, market_catalog=catalog)

    assert len(rows) == 1
    assert rows[0].market == "goals_ft"
    assert rows[0].selection == "over"
    assert rows[0].line == 2.5


def test_normalize_market_keeps_periods_separate():
    assert normalize_market("Over Under", "Over", "fulltime") == ("goals_ft", "over")
    assert normalize_market("Over Under", "Over", "1st half") == ("goals_1h", "over")
    assert normalize_market("Full Time Result", "1", "fulltime") == ("1x2_ft", "home")


def test_parse_oddspapi_ignores_suspended_bookmaker():
    payload = {"fixtureId": "id-demo", "bookmakerOdds": {"betano.pe": {"suspended": True}}}
    assert parse_odds(payload) == []


def test_parse_oddspapi_ignores_inactive_bookmaker():
    payload = {"fixtureId": "id-demo", "bookmakerOdds": {"betano.pe": {"bookmakerIsActive": False, "suspended": False}}}
    assert parse_odds(payload) == []
