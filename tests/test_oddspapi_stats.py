import pytest

from betano_analyzer import oddspapi_stats


@pytest.mark.asyncio
async def test_hydrate_team_history_persists_bounded_scores(monkeypatch):
    calls = []

    async def fake_fetch(provider, path, params=None, timeout=15.0):
        calls.append((path, params))
        if path == "/v4/fixtures":
            return [{"id": "fx-1", "homeTeam": "A", "awayTeam": "B", "startTime": "2026-09-10T18:00:00Z"}]
        if path == "/v4/scores":
            return {"homeScore": 2, "awayScore": 1}
        raise AssertionError(path)

    inserted = []
    monkeypatch.setattr(oddspapi_stats, "fetch_json", fake_fetch)
    monkeypatch.setattr(oddspapi_stats, "record_history", lambda rows, source: inserted.extend(rows) or len(rows))

    result = await oddspapi_stats.hydrate_team_history(participant_id="123", limit=1)

    assert result["status"] == "OK"
    assert result["fixtures_considered"] == 1
    assert result["score_requests"] == 1
    assert result["history_rows"] == 2
    assert result["inserted"] == 2
    assert calls[0][1]["statusId"] == 2
    assert inserted[0]["goals_for"] == 2
    assert inserted[1]["goals_for"] == 1


@pytest.mark.asyncio
async def test_hydrate_team_history_rejects_large_limit():
    with pytest.raises(ValueError):
        await oddspapi_stats.hydrate_team_history(participant_id="123", limit=11)
