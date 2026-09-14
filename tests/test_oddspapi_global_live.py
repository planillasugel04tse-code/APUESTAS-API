import pytest

from betano_analyzer import oddspapi_global_live as live


@pytest.mark.asyncio
async def test_discover_live_bookmakers_filters_and_caps(monkeypatch):
    async def fake_bookmakers(*, force=False):
        return [
            {"slug": "book-a", "has_live_odds": True},
            {"slug": "book-b", "has_live_odds": False},
            {"slug": "book-c", "has_live_odds": True},
            {"slug": "book-a", "has_live_odds": True},
        ]
    monkeypatch.setattr(live, "fetch_bookmakers", fake_bookmakers)
    selected, discovered = await live.discover_live_bookmakers(limit=2)
    assert selected == ["book-a", "book-c"]
    assert discovered == 2


@pytest.mark.asyncio
async def test_discover_live_bookmakers_supports_api_flags(monkeypatch):
    async def fake_bookmakers(*, force=False):
        return {"data": [{"key": "book-a", "hasLiveOdds": True}]}
    monkeypatch.setattr(live, "fetch_bookmakers", fake_bookmakers)
    selected, discovered = await live.discover_live_bookmakers(limit=5)
    assert selected == ["book-a"]
    assert discovered == 1


@pytest.mark.asyncio
async def test_sync_global_live_processes_all_selected_fixtures(monkeypatch):
    class Fixture:
        def __init__(self, external_id):
            self.external_id = external_id

    fixtures = [Fixture(str(i)) for i in range(45)]
    calls = []

    async def fake_bookmakers(limit=10):
        return ["book-a"], 1

    async def fake_fixtures(**kwargs):
        return fixtures

    async def fake_catalog():
        return []

    async def fake_odds(external_id, bookmakers, **kwargs):
        calls.append((external_id, tuple(bookmakers)))
        return {bookmakers[0]: []}

    monkeypatch.setattr(live, "discover_live_bookmakers", fake_bookmakers)
    monkeypatch.setattr(live, "fetch_fixtures", fake_fixtures)
    monkeypatch.setattr(live, "fetch_market_catalog", fake_catalog)
    monkeypatch.setattr(live, "fetch_odds_multi_bookmaker", fake_odds)
    monkeypatch.setattr(live, "save_matches", lambda items: (len(items), len(items)))
    monkeypatch.setattr(live, "save_odds", lambda items: (len(items), len(items)))
    monkeypatch.setattr(live, "_set_live_status", lambda ids: None)

    result = await live.sync_global_live()
    assert result.fixtures_saved == 45
    assert len(calls) == 45
    assert calls[-1][0] == "44"
    assert result.odds_requests == 45
