import pytest
from fastapi.testclient import TestClient

from betano_analyzer.main import app
from betano_analyzer.sync_service import SyncSummary


@pytest.fixture
def client():
    return TestClient(app)


def test_pre_match_endpoint_uses_stored_odds_only(client):
    response = client.get("/api/v1/arbitrage/pre-match", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "pre_match"
    assert body["refresh"] == "stored_odds_only"
    assert "opportunities" in body


def test_live_endpoint_requests_live_only(monkeypatch, client):
    calls = {}

    async def fake_sync(**kwargs):
        calls.update(kwargs)
        return SyncSummary(8, 0, 0, 0, 0, 0, 0)

    monkeypatch.setattr("betano_analyzer.sync_service.sync_oddspapi_betano_pe", fake_sync)

    response = client.post("/api/v1/arbitrage/live", params={"limit": 5, "hours": 1, "limit_matches": 3})

    assert response.status_code == 200
    assert calls["include_live"] is True
    assert calls["live_only"] is True
    assert calls["hours"] == 1
    assert calls["limit_matches"] == 3
    assert response.json()["refreshed_on_demand"] is True
