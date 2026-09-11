from types import SimpleNamespace

from fastapi.testclient import TestClient

from betano_analyzer.main import app


def test_bookmaker_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/bookmakers" in paths
    assert "/api/v1/bookmakers/selected" in paths
    assert "/api/v1/bookmakers/peru" in paths
    assert "/api/v1/bookmakers/peru/names" in paths
    assert "/bookmakers" in paths


def test_sync_accepts_peru_alias(monkeypatch):
    import betano_analyzer.api as api

    async def fake_peru_bookmakers():
        return ["Betano PE", "Inkabet"]

    async def fake_sync(books, include_live, limit_per_league):
        assert books == ["Betano PE", "Inkabet"]
        assert include_live is False
        assert limit_per_league == 20
        return SimpleNamespace(matches_seen=2, matches_saved=2, odds_seen=4, odds_saved=4)

    monkeypatch.setattr(api, "peru_bookmakers", fake_peru_bookmakers)
    monkeypatch.setattr(api, "sync_odds", fake_sync)
    client = TestClient(app)
    response = client.post("/api/v1/sync/odds?bookmakers=peru&limit_per_league=20")
    assert response.status_code == 200
    assert response.json()["bookmakers_requested"] == ["Betano PE", "Inkabet"]
