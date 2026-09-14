import pytest

import betano_analyzer.oddspapi_odds as client


@pytest.mark.asyncio
async def test_get_odds_batches_bookmakers_in_one_request(monkeypatch):
    calls = []

    async def fake_fetch(provider, path, params=None, timeout=15.0):
        calls.append((provider, path, params))
        return {"fixtureId": "fx1", "bookmakerOdds": []}

    monkeypatch.setattr(client, "fetch_json", fake_fetch)
    client.clear_cache()

    result = await client.get_odds(
        "fx1",
        bookmakers=["betsson", "betano.pe", "pinnacle", "betsson"],
    )

    assert result["fixtureId"] == "fx1"
    assert len(calls) == 1
    assert calls[0][0] == "oddspapi"
    assert calls[0][1] == "/v4/odds"
    assert calls[0][2]["bookmakers"] == "betsson,betano.pe,pinnacle"
    assert calls[0][2]["oddsFormat"] == "decimal"


@pytest.mark.asyncio
async def test_positive_cache_ttl_prevents_duplicate_billable_calls(monkeypatch):
    calls = []

    async def fake_fetch(provider, path, params=None, timeout=15.0):
        calls.append(params)
        return {"fixtureId": "fx2", "value": len(calls)}

    monkeypatch.setattr(client, "fetch_json", fake_fetch)
    client.clear_cache()

    first = await client.get_odds("fx2", bookmakers="betano.pe,betsson", cache_seconds=30)
    second = await client.get_odds("fx2", bookmakers="betsson,betano.pe", cache_seconds=30)

    assert first == second
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(monkeypatch):
    calls = []

    async def fake_fetch(provider, path, params=None, timeout=15.0):
        calls.append(params)
        return {"fixtureId": "fx3", "value": len(calls)}

    monkeypatch.setattr(client, "fetch_json", fake_fetch)
    client.clear_cache()

    await client.get_odds("fx3", bookmakers="pinnacle", cache_seconds=30)
    fresh = await client.get_odds("fx3", bookmakers="pinnacle", cache_seconds=30, force_refresh=True)

    assert fresh["value"] == 2
    assert len(calls) == 2
