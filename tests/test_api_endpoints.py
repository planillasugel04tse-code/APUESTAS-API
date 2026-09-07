from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from betano_analyzer.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_tipster_match_odds_pick_and_bet():
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    match = client.post("/api/v1/matches", json={
        "external_id": f"test-{suffix}",
        "competition": "Premier League",
        "home_team": "Test United",
        "away_team": "Test City",
        "kickoff": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    })
    assert match.status_code == 200
    match_id = match.json()["id"]

    tipster = client.post("/api/v1/tipsters", json={"name": f"TestTipster-{suffix}", "source": "test"})
    assert tipster.status_code == 200

    odds = client.post("/api/v1/odds", json={
        "match_id": match_id,
        "bookmaker": "TestBook",
        "market": "over",
        "selection": "2.0",
        "odds": 1.75,
    })
    assert odds.status_code == 200

    pick = client.post("/api/v1/picks", json={
        "match_id": match_id,
        "tipster_id": tipster.json()["id"],
        "original_market": "over",
        "original_selection": "2.5",
        "original_odds": 1.60,
        "conservative_market": "over",
        "conservative_selection": "2.0",
        "conservative_odds": 1.75,
        "confidence": 0.80,
    })
    assert pick.status_code == 200

    bet = client.post("/api/v1/bets", json={
        "match_id": match_id,
        "pick_id": pick.json()["id"],
        "selection": "over 2.0",
        "odds": 1.75,
        "stake": 10,
        "placed_at": datetime.now(timezone.utc).isoformat(),
    })
    assert bet.status_code == 200
    assert bet.json()["potential_return"] == 17.5

    settled = client.patch(f"/api/v1/bets/{bet.json()['id']}/settle", json={"result": "won"})
    assert settled.status_code == 200
    assert settled.json()["result"] == "won"
