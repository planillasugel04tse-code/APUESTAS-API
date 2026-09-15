from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .db import connect, initialize
from .oddspapi_io import fetch_fixtures
from .providers import fetch_json
from .team_statistics import build_match_probability, record_history


@dataclass(frozen=True)
class HistoryHydrationSummary:
    match_id: int
    external_fixture_id: str
    home_team: str
    away_team: str
    fixtures_found: int
    matches_saved: int
    score_requests: int
    status: str
    source: str = "oddspapi"
    no_invention: bool = True


def _fixture_row(match_id: int) -> tuple[str, str, str, str] | None:
    initialize()
    with connect() as db:
        row = db.execute(
            "SELECT external_id, home_team, away_team, competition FROM matches WHERE id=?",
            (match_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row["external_id"]), str(row["home_team"]), str(row["away_team"]), str(row["competition"] or "")


def _participant_ids(payload: Any) -> list[int]:
    if not isinstance(payload, dict):
        return []
    candidates: list[Any] = []
    for key in ("participants", "teams", "participantsData"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    ids: list[int] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        raw = item.get("id") or item.get("participantId") or item.get("teamId")
        if raw is not None:
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
    return list(dict.fromkeys(ids))


def _team_name(item: dict[str, Any]) -> str | None:
    for key in ("name", "teamName", "participantName"):
        value = item.get(key)
        if value:
            return str(value)
    nested = item.get("team") or item.get("participant")
    if isinstance(nested, dict):
        return _team_name(nested)
    return None


def _extract_score(payload: Any) -> tuple[int, int] | None:
    """Extract a final home/away score from common OddsPapi score shapes."""
    if not isinstance(payload, dict):
        return None
    for container_key in ("score", "scores", "result", "fixtureScore"):
        value = payload.get(container_key)
        if isinstance(value, dict):
            home = value.get("home") or value.get("homeScore") or value.get("homeGoals")
            away = value.get("away") or value.get("awayScore") or value.get("awayGoals")
            if isinstance(home, dict): home = home.get("current") or home.get("display") or home.get("goals")
            if isinstance(away, dict): away = away.get("current") or away.get("display") or away.get("goals")
            try:
                if home is not None and away is not None:
                    return int(home), int(away)
            except (TypeError, ValueError):
                pass
    # Some payloads expose home/away score directly.
    for hkey, akey in (("homeScore", "awayScore"), ("homeGoals", "awayGoals")):
        try:
            if payload.get(hkey) is not None and payload.get(akey) is not None:
                return int(payload[hkey]), int(payload[akey])
        except (TypeError, ValueError):
            pass
    return None


def _extract_fixture(item: Any) -> tuple[str, str, str, str, str, int | None, int | None] | None:
    if not isinstance(item, dict):
        return None
    fixture_id = item.get("id") or item.get("fixtureId")
    home = item.get("homeTeam") or item.get("home") or {}
    away = item.get("awayTeam") or item.get("away") or {}
    home_name = _team_name(home) if isinstance(home, dict) else str(home or "")
    away_name = _team_name(away) if isinstance(away, dict) else str(away or "")
    played_at = item.get("startTime") or item.get("kickoff") or item.get("date")
    score = _extract_score(item)
    if fixture_id is None or not home_name or not away_name:
        return None
    return str(fixture_id), home_name, away_name, str(played_at or ""), str(item.get("status") or "finished"), score[0] if score else None, score[1] if score else None


async def _fixture_details(external_fixture_id: str) -> dict[str, Any]:
    payload = await fetch_json("oddspapi", "/v4/fixture", {"fixtureId": external_fixture_id})
    return payload if isinstance(payload, dict) else {}


async def _scores(external_fixture_id: str) -> tuple[int, int] | None:
    payload = await fetch_json("oddspapi", "/v4/scores", {"fixtureId": external_fixture_id})
    return _extract_score(payload)


async def hydrate_match_history(match_id: int, *, max_matches: int = 6, max_requests: int = 16) -> HistoryHydrationSummary:
    """Hydrate recent finished team history only when explicitly requested.

    The operation is deliberately bounded: one fixture-details request, up to
    two participant fixture searches, and only the score requests still needed.
    Existing rows are deduplicated by the database. No score is invented when
    OddsPapi does not return one.
    """
    row = _fixture_row(match_id)
    if row is None:
        raise ValueError("Partido no encontrado")
    external_id, home_team, away_team, _ = row
    if max_matches < 1 or max_matches > 10:
        raise ValueError("max_matches debe estar entre 1 y 10")
    if max_requests < 3 or max_requests > 30:
        raise ValueError("max_requests debe estar entre 3 y 30")

    used = 1
    details = await _fixture_details(external_id)
    participants = _participant_ids(details)
    if not participants:
        return HistoryHydrationSummary(match_id, external_id, home_team, away_team, 0, 0, 0, "NO_PARTICIPANTS")

    fixtures: dict[str, Any] = {}
    per_team = max(1, max_matches // min(2, len(participants)))
    for participant_id in participants[:2]:
        if used >= max_requests:
            break
        found = await fetch_fixtures(participantId=participant_id, statusId=2, limit=per_team)
        used += 1
        for fixture in found:
            fixtures[str(fixture.external_id)] = fixture

    score_requests = 0
    history: list[dict[str, Any]] = []
    for fixture in list(fixtures.values())[:max_matches]:
        parsed = None
        if isinstance(fixture, dict):
            parsed = _extract_fixture(fixture)
        else:
            # fetch_fixtures returns normalized objects; fetch score separately.
            fixture_id = str(fixture.external_id)
            hname, aname = str(fixture.home_team), str(fixture.away_team)
            played_at = str(fixture.kickoff)
            if used < max_requests:
                parsed_score = await _scores(fixture_id)
                used += 1
                score_requests += 1
                if parsed_score:
                    history.extend((
                        {"team": hname, "opponent": aname, "goals_for": parsed_score[0], "goals_against": parsed_score[1], "is_home": True, "played_at": played_at, "external_match_id": fixture_id},
                        {"team": aname, "opponent": hname, "goals_for": parsed_score[1], "goals_against": parsed_score[0], "is_home": False, "played_at": played_at, "external_match_id": fixture_id},
                    ))
            continue
        if parsed is None:
            continue
        fixture_id, hname, aname, played_at, _, home_score, away_score = parsed
        if home_score is None or away_score is None:
            if used >= max_requests:
                continue
            score = await _scores(fixture_id)
            used += 1
            score_requests += 1
            if score:
                home_score, away_score = score
        if home_score is None or away_score is None:
            continue
        history.extend((
            {"team": hname, "opponent": aname, "goals_for": home_score, "goals_against": away_score, "is_home": True, "played_at": played_at, "external_match_id": fixture_id},
            {"team": aname, "opponent": hname, "goals_for": away_score, "goals_against": home_score, "is_home": False, "played_at": played_at, "external_match_id": fixture_id},
        ))

    saved = record_history(history, source="oddspapi") if history else 0
    return HistoryHydrationSummary(match_id, external_id, home_team, away_team, len(fixtures), saved, score_requests, "OK" if saved else "NO_SCORES")
