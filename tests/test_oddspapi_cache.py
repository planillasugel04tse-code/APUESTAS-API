import pytest

import betano_analyzer.oddspapi_io as oddspapi_io


@pytest.mark.asyncio
async def test_odds_cache_is_order_independent(monkeypatch):
    calls = []
    payload = {
        "fixtureId": "f1",
        "bookmakerOdds": {
            "betano.pe": {"bookmakerIsActive": True, "suspended": False, "markets": {}},
            "pinnacle": {"bookmakerIsActive": True, "suspended": False, "markets": {}},
        },
    }

    async def fake_fetch_json(provider, path, params=None):
        calls.append((provider, path, params))
        return payload

    monkeypatch.setattr(oddspapi_io, "fetch_json", fake_fetch_json)
    oddspapi_io._ODDS_CACHE.clear()

    await oddspapi_io.fetch_odds_multi_bookmaker("f1", ["betano.pe", "pinnacle"], cache_ttl=30)
    await oddspapi_io.fetch_odds_multi_bookmaker("f1", ["pinnacle", "betano.pe"], cache_ttl=30)

    assert len(calls) == 1
    assert calls[0][2]["bookmakers"] == "betano.pe,pinnacle"
