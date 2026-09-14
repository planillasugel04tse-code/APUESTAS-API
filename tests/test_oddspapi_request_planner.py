import pytest

from betano_analyzer import oddspapi_io


@pytest.mark.asyncio
async def test_multi_bookmaker_odds_uses_one_provider_call(monkeypatch):
    calls = []
    payload = {
        "fixtureId": "f1",
        "bookmakerOdds": {
            "betano.pe": {"bookmakerIsActive": True, "markets": {}},
            "pinnacle": {"bookmakerIsActive": True, "markets": {}},
        },
    }

    async def fake_fetch(provider, path, params=None, timeout=15.0):
        calls.append((provider, path, params))
        return payload

    oddspapi_io._ODDS_CACHE.clear()
    monkeypatch.setattr(oddspapi_io, "fetch_json", fake_fetch)
    result = await oddspapi_io.fetch_odds_multi_bookmaker("f1", ["betano.pe", "pinnacle"])

    assert set(result) == {"betano.pe", "pinnacle"}
    assert len(calls) == 1
    assert calls[0][1] == "/v4/odds"
    assert calls[0][2]["bookmakers"] == "betano.pe,pinnacle"


@pytest.mark.asyncio
async def test_same_fixture_and_bookmakers_are_cached(monkeypatch):
    calls = []

    async def fake_fetch(provider, path, params=None, timeout=15.0):
        calls.append(1)
        return {"fixtureId": "f1", "bookmakerOdds": {}}

    oddspapi_io._ODDS_CACHE.clear()
    monkeypatch.setattr(oddspapi_io, "fetch_json", fake_fetch)
    await oddspapi_io.fetch_odds_multi_bookmaker("f1", ["pinnacle", "betano.pe"])
    await oddspapi_io.fetch_odds_multi_bookmaker("f1", ["betano.pe", "pinnacle"])

    assert len(calls) == 1
