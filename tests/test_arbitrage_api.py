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


def test_live_peru_endpoint_keeps_provider_batching_internal(monkeypatch, client):
    calls = {}

    async def fake_sync(**kwargs):
        calls.update(kwargs)
        return SyncSummary(8, 0, 0, 0, 0, 0, 0)

    monkeypatch.setattr("betano_analyzer.sync_service.sync_oddspapi_betano_pe", fake_sync)
    response = client.post("/api/v1/arbitrage/live", params={"limit": 5, "hours": 1, "scope": "peru"})
    assert response.status_code == 200
    assert calls["include_live"] is True
    assert calls["live_only"] is True
    assert calls["hours"] == 1
    assert calls["limit_matches"] == 20
    assert response.json()["refresh_scope"] == "peru"


def test_live_world_endpoint_hides_match_batch_limit(monkeypatch, client):
    calls = {}

    async def fake_global(**kwargs):
        calls.update(kwargs)
        return type("Summary", (), {"__dict__": {"bookmakers_discovered": 12, "bookmakers_selected": 10, "fixtures_seen": 45, "fixtures_saved": 45, "odds_seen": 20, "odds_saved": 20, "bookmaker_cap": 10, "scope": "world", "sport": "football"}})()

    monkeypatch.setattr("betano_analyzer.arbitrage_api.sync_global_live", fake_global)
    monkeypatch.setattr("betano_analyzer.arbitrage_api.find_arbitrage", lambda *a, **kw: [])
    response = client.post("/api/v1/arbitrage/live", params={"limit": 5, "hours": 1, "scope": "world"})
    assert response.status_code == 200
    assert calls == {"hours": 1, "bookmaker_cap": 10}
    assert response.json()["refresh_scope"] == "world"
    assert response.json()["sync"]["fixtures_saved"] == 45


def test_verify_endpoint_refreshes_only_requested_match(monkeypatch, client):
    calls = {}

    async def fake_verify(match_id):
        calls["match_id"] = match_id
        return SyncSummary(8, 1, 0, 3, 3, 0, 0)

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
