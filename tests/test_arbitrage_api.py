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


def test_verify_endpoint_refreshes_only_requested_match(monkeypatch, client):
    calls = {}

    async def fake_verify(match_id):
        calls["match_id"] = match_id
        return SyncSummary(8, 1, 0, 3, 3, 0, 0)

    # match_id=42 is a synthetic test fixture: we must ensure find_arbitrage
    # returns nothing for it regardless of what is stored in the local DB.
    monkeypatch.setattr("betano_analyzer.arbitrage_api.find_arbitrage", lambda *a, **kw: [])
    monkeypatch.setattr("betano_analyzer.sync_service.verify_oddspapi_betano_pe_match", fake_verify)
    response = client.post("/api/v1/arbitrage/verify/42", params={"limit": 5})

    assert response.status_code == 200
    assert calls["match_id"] == 42
    body = response.json()
    assert body["match_id"] == 42
    assert body["odds_seen"] == 3
    assert body["odds_saved"] == 3
    assert body["surebet_confirmed"] is False
