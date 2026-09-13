import pytest

from betano_analyzer.oddspapi_global_live import discover_live_bookmakers


@pytest.mark.asyncio
async def test_discover_live_bookmakers_filters_and_caps(monkeypatch):
    async def fake_fetch_json(*args, **kwargs):
        return [
            {"slug": "book-a", "has_live_odds": True},
            {"slug": "book-b", "has_live_odds": False},
            {"slug": "book-c", "has_live_odds": True},
            {"slug": "book-a", "has_live_odds": True},
        ]

    monkeypatch.setattr("betano_analyzer.oddspapi_global_live.fetch_json", fake_fetch_json)

    selected, discovered = await discover_live_bookmakers(limit=2)

    assert selected == ["book-a", "book-c"]
    assert discovered == 2


@pytest.mark.asyncio
async def test_discover_live_bookmakers_supports_api_flags(monkeypatch):
    async def fake_fetch_json(*args, **kwargs):
        return {"data": [{"key": "book-a", "hasLiveOdds": True}]}

    monkeypatch.setattr("betano_analyzer.oddspapi_global_live.fetch_json", fake_fetch_json)

    selected, discovered = await discover_live_bookmakers(limit=5)

    assert selected == ["book-a"]
    assert discovered == 1
