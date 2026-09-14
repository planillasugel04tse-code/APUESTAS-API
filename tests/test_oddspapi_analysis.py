from betano_analyzer.oddspapi_analysis import analyze_odds_payload


def _payload():
    return {
        "fixtureId": "fixture-1",
        "participant1Name": "Equipo A",
        "participant2Name": "Equipo B",
        "hasOdds": True,
        "bookmakerOdds": {
            "betano.pe": {
                "markets": [{
                    "marketType": "1x2",
                    "marketName": "Full Time Result",
                    "outcomes": [
                        {"outcomeName": "1", "price": 2.20, "mainLine": True},
                        {"outcomeName": "X", "price": 3.60, "mainLine": True},
                        {"outcomeName": "2", "price": 3.40, "mainLine": True},
                    ],
                }]
            },
            "betsson": {
                "markets": [{
                    "marketType": "1x2",
                    "marketName": "Full Time Result",
                    "outcomes": [
                        {"outcomeName": "1", "price": 2.10, "mainLine": True},
                        {"outcomeName": "X", "price": 3.70, "mainLine": True},
                        {"outcomeName": "2", "price": 3.60, "mainLine": True},
                    ],
                }]
            },
            "pinnacle": {
                "markets": [{
                    "marketType": "1x2",
                    "marketName": "Full Time Result",
                    "outcomes": [
                        {"outcomeName": "1", "price": 2.05, "mainLine": True},
                        {"outcomeName": "X", "price": 3.45, "mainLine": True},
                        {"outcomeName": "2", "price": 3.35, "mainLine": True},
                    ],
                }]
            },
        },
    }


def test_detects_three_way_surebet_and_stakes():
    result = analyze_odds_payload(
        _payload(),
        bankroll=100,
        execution_bookmakers=["betano.pe", "betsson"],
        reference_bookmakers=["pinnacle"],
    )
    assert result["fixture_id"] == "fixture-1"
    assert len(result["surebets"]) == 1
    arb = result["surebets"][0]
    assert arb["profit_percent"] > 0
    assert sum(item["stake"] for item in arb["outcomes"].values()) == 100.0
    assert {item["bookmaker"] for item in arb["outcomes"].values()} == {"betano.pe", "betsson"}

    edges = {row["outcome"]: row["edge_percent"] for row in result["reference_edge"]}
    assert edges["home"] > 0


def test_reference_only_does_not_create_execution_surebet():
    result = analyze_odds_payload(
        _payload(),
        execution_bookmakers=["betano.pe"],
        reference_bookmakers=["pinnacle"],
    )
    assert result["surebets"] == []
