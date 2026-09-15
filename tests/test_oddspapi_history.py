from types import SimpleNamespace

import pytest

from betano_analyzer import oddspapi_history as history


@pytest.mark.asyncio
async def test_hydrate_match_history_is_bounded_and_persists(monkeypatch, tmp_path):
    from betano_analyzer import db

    db_path = tmp_path / "stats.sqlite3"
    monkeypatch.setenv("DB_PATH", str(db_path))
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO matches(external_id, competition, home_team, away_team, kickoff) VALUES(?,?,?,?,?)",
            ("fx-1", "Liga 1 Peru", "Alianza", "Cristal", "2026-09-15T20:00:00+00:00"),
        )
        match_id = conn.execute("SELECT id FROM matches WHERE external_id='fx-1'").fetchone()[0]
        conn.commit()

    calls = []

    async def fake_fetch_json(provider, path, params=None, timeout=15.0):
        calls.append(path)
        if path == "/v4/fixture":
            return {"participants": [{"id": 10, "name": "Alianza"}, {"id": 20, "name": "Cristal"}]}
        if path == "/v4/scores":
            return {"score": {"home": 2, "away": 1}}
        raise AssertionError(path)

    async def fake_fetch_fixtures(**params):
        calls.append("/v4/fixtures")
        assert params["statusId"] == 2
        return [SimpleNamespace(external_id="old-1", home_team="Alianza", away_team="Other", kickoff="2026-09-10T00:00:00+00:00")]

    monkeypatch.setattr(history, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(history, "fetch_fixtures", fake_fetch_fixtures)

    result = await history.hydrate_match_history(match_id, max_matches=1, max_requests=5)

    assert result.status == "OK"
    assert result.matches_saved == 2
    assert result.score_requests == 1
    assert calls.count("/v4/fixtures") == 2
    assert len(calls) <= 4


@pytest.mark.asyncio
async def test_hydrate_requires_participants(monkeypatch, tmp_path):
    from betano_analyzer import db

    db_path = tmp_path / "stats.sqlite3"
    monkeypatch.setenv("DB_PATH", str(db_path))
    db.initialize()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO matches(external_id, competition, home_team, away_team, kickoff) VALUES(?,?,?,?,?)",
            ("fx-2", "Liga 1 Peru", "A", "B", "2026-09-15T20:00:00+00:00"),
        )
        match_id = conn.execute("SELECT id FROM matches WHERE external_id='fx-2'").fetchone()[0]
        conn.commit()

    async def fake_fetch_json(*args, **kwargs):
        return {"participants": []}

    monkeypatch.setattr(history, "fetch_json", fake_fetch_json)
    result = await history.hydrate_match_history(match_id)
    assert result.status == "NO_PARTICIPANTS"
    assert result.matches_saved == 0
