from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from .dashboard import Period, period_range
from .db import connect
from .radar import build_radar
from .schemas import BetCreate, MatchCreate, PickCreate

router = APIRouter(prefix="/api/v1")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def date_filters(period: Period):
    start, end = period_range(period)
    return start.isoformat() if start else None, end.isoformat() if end else None


@router.post("/matches")
def create_match(data: MatchCreate):
    with connect() as db:
        cur = db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            (data.external_id, data.competition, data.home_team, data.away_team, data.kickoff, data.status),
        )
        return {"id": cur.lastrowid, **data.model_dump()}


@router.post("/picks")
def create_pick(data: PickCreate):
    with connect() as db:
        cur = db.execute(
            """INSERT INTO picks(match_id,tipster_id,original_market,original_selection,
            original_odds,conservative_market,conservative_selection,conservative_odds,confidence,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (*data.model_dump().values(), now()),
        )
        return {"id": cur.lastrowid, **data.model_dump()}


@router.post("/bets")
def create_bet(data: BetCreate):
    with connect() as db:
        cur = db.execute(
            """INSERT INTO bets(match_id,pick_id,selection,odds,stake,result,cashout,placed_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (*data.model_dump().values(),),
        )
        return {"id": cur.lastrowid, **data.model_dump(), "potential_return": data.stake * data.odds}


@router.get("/bets/summary")
def bets_summary(period: Period = Query(default=Period.TODOS)):
    start, end = date_filters(period)
    with connect() as db:
        query = "SELECT stake, odds, result, cashout, placed_at FROM bets"
        params = []
        clauses = []
        if start:
            clauses.append("date(placed_at) >= date(?)")
            params.append(start)
        if end:
            clauses.append("date(placed_at) <= date(?)")
            params.append(end)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = db.execute(query, params).fetchall()

    settled = [r for r in rows if r["result"] != "pending"]
    wins = sum(1 for r in settled if r["result"] == "won")
    losses = sum(1 for r in settled if r["result"] == "lost")
    settled_stake = sum(r["stake"] for r in settled)
    returns = sum((r["stake"] * r["odds"] if r["result"] == "won" else r["cashout"] or 0) for r in settled)
    net = returns - settled_stake
    return {
        "period": period.value,
        "from": start,
        "to": end,
        "bets": len(rows),
        "settled": len(settled),
        "wins": wins,
        "losses": losses,
        "pending": len(rows) - len(settled),
        "stake": sum(r["stake"] for r in rows),
        "returns": returns,
        "net": net,
        "roi": net / settled_stake if settled_stake else 0,
        "hit_rate": wins / len(settled) if settled else 0,
    }


@router.get("/opportunities")
def opportunities(limit: int = Query(default=20, ge=1, le=100)):
    return build_radar(limit=limit)


@router.get("/dashboard/periods")
def dashboard_periods():
    return {"periods": [
        {"id": "hoy", "label": "HOY"},
        {"id": "lunes-viernes", "label": "LUNES A VIERNES"},
        {"id": "sabado-domingo", "label": "SÁBADO Y DOMINGO"},
        {"id": "mes", "label": "MES"},
        {"id": "3-meses", "label": "3 MESES"},
        {"id": "6-meses", "label": "6 MESES"},
        {"id": "todos", "label": "TODOS"},
    ]}
