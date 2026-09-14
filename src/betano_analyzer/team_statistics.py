from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Iterable

from .db import connect, initialize
from .statistical_engine import TeamMatch, build_report, probability_for_selection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_history(items: Iterable[dict[str, Any]], *, source: str = "supplied") -> int:
    initialize()
    rows = list(items)
    inserted = 0
    with connect() as db:
        for item in rows:
            team = str(item["team"]).strip()
            opponent = str(item["opponent"]).strip()
            if not team or not opponent:
                continue
            cur = db.execute(
                """INSERT OR IGNORE INTO team_match_history
                (team, opponent, goals_for, goals_against, is_home, played_at, external_match_id, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (team, opponent, int(item["goals_for"]), int(item["goals_against"]), 1 if item.get("is_home", True) else 0,
                 item.get("played_at"), item.get("external_match_id"), source, _now()),
            )
            inserted += int(cur.rowcount > 0)
        db.commit()
    return inserted


def get_team_history(team: str, *, limit: int = 20) -> list[TeamMatch]:
    initialize()
    with connect() as db:
        rows = db.execute(
            "SELECT goals_for, goals_against, is_home FROM team_match_history WHERE lower(team)=lower(?) ORDER BY played_at DESC, id DESC LIMIT ?",
            (team.strip(), limit),
        ).fetchall()
    return [TeamMatch(int(r["goals_for"]), int(r["goals_against"]), bool(r["is_home"])) for r in rows]


def build_team_report(team: str, *, limit: int = 20, min_sample: int = 5):
    history = get_team_history(team, limit=limit)
    return build_report(history, min_sample=min_sample)


def build_match_probability(home_team: str, away_team: str, market: str, selection: str, *, limit: int = 20, min_sample: int = 5) -> dict[str, Any]:
    home = build_team_report(home_team, limit=limit, min_sample=min_sample)
    away = build_team_report(away_team, limit=limit, min_sample=min_sample)
    probabilities = [p for p in (probability_for_selection(home, market, selection), probability_for_selection(away, market, selection)) if p is not None]
    probability = sum(probabilities) / len(probabilities) if probabilities else None
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_report": asdict(home),
        "away_report": asdict(away),
        "selection_probability": round(probability, 4) if probability is not None else None,
        "status": "OK" if probability is not None else "DATOS_INSUFICIENTES",
        "source": "stored_team_match_history",
        "no_invention": True,
    }
