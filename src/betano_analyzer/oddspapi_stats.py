from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .db import initialize
from .providers import fetch_json
from .team_statistics import record_history


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "fixtures", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _value(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return None


def _participant_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _value(value, "name", "shortName", "displayName", "teamName")
    return None


def _fixture_teams(fixture: dict[str, Any]) -> tuple[str | None, str | None]:
    home = _value(fixture, "homeTeam", "home", "homeParticipant")
    away = _value(fixture, "awayTeam", "away", "awayParticipant")
    if home is None or away is None:
        participants = fixture.get("participants")
        if isinstance(participants, list) and len(participants) >= 2:
            home = participants[0]
            away = participants[1]
    return _participant_name(home), _participant_name(away)


def _score_pair(payload: Any) -> tuple[int | None, int | None]:
    if isinstance(payload, dict):
        home = _value(payload, "home", "homeScore", "home_score", "scoreHome")
        away = _value(payload, "away", "awayScore", "away_score", "scoreAway")
        if isinstance(home, dict):
            home = _value(home, "current", "display", "value", "score")
        if isinstance(away, dict):
            away = _value(away, "current", "display", "value", "score")
        if isinstance(home, (int, float)) and isinstance(away, (int, float)):
            return int(home), int(away)
        for key in ("score", "scores", "data", "result"):
            nested = payload.get(key)
            pair = _score_pair(nested)
            if pair != (None, None):
                return pair
    if isinstance(payload, list):
        for item in payload:
            pair = _score_pair(item)
            if pair != (None, None):
                return pair
    return None, None


def _played_at(fixture: dict[str, Any]) -> str | None:
    value = _value(fixture, "startTime", "kickoff", "date", "startDate", "playedAt")
    return str(value) if value is not None else None


async def hydrate_team_history(*, participant_id: str, limit: int = 5) -> dict[str, Any]:
    """Hydrate a small recent finished-match sample from OddsPapi.

    This is deliberately on-demand and bounded: it only requests finished
    fixtures for one participant and then asks for scores for those fixtures.
    No global historical scan is performed.
    """
    if not str(participant_id).strip():
        raise ValueError("participant_id es obligatorio")
    if not 1 <= limit <= 10:
        raise ValueError("limit debe estar entre 1 y 10")

    initialize()
    fixtures_payload = await fetch_json(
        "oddspapi",
        "/v4/fixtures",
        params={"participantId": str(participant_id), "statusId": 2},
    )
    fixtures = _rows(fixtures_payload)[:limit]
    history: list[dict[str, Any]] = []
    score_requests = 0
    for fixture in fixtures:
        fixture_id = _value(fixture, "id", "fixtureId", "externalId")
        if fixture_id is None:
            continue
        home, away = _fixture_teams(fixture)
        if not home or not away:
            continue
        score_payload = await fetch_json("oddspapi", "/v4/scores", params={"fixtureId": str(fixture_id)})
        score_requests += 1
        home_goals, away_goals = _score_pair(score_payload)
        if home_goals is None or away_goals is None:
            continue
        played_at = _played_at(fixture)
        external_id = str(fixture_id)
        history.extend([
            {"team": home, "opponent": away, "goals_for": home_goals, "goals_against": away_goals,
             "is_home": True, "played_at": played_at, "external_match_id": external_id},
            {"team": away, "opponent": home, "goals_for": away_goals, "goals_against": home_goals,
             "is_home": False, "played_at": played_at, "external_match_id": external_id},
        ])

    inserted = record_history(history, source="oddspapi") if history else 0
    return {
        "status": "OK" if inserted or history else "NO_DATA",
        "participant_id": str(participant_id),
        "fixtures_considered": len(fixtures),
        "score_requests": score_requests,
        "history_rows": len(history),
        "inserted": inserted,
        "source": "oddspapi",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "no_invention": True,
    }
