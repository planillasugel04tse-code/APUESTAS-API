from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from .db import connect
from .schemas import BetCreate, MatchCreate, PickCreate

router = APIRouter(prefix="/api/v1")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        potential_return = data.stake * data.odds
        return {"id": cur.lastrowid, **data.model_dump(), "potential_return": potential_return}


@router.get("/bets/summary")
def bets_summary():
    with connect() as db:
        rows = db.execute("SELECT stake, odds, result, cashout FROM bets").fetchall()
    stake = sum(r["stake"] for r in rows)
    settled = [r for r in rows if r["result"] != "pending"]
    wins = sum(1 for r in settled if r["result"] == "won")
    losses = sum(1 for r in settled if r["result"] == "lost")
    returns = sum((r["stake"] * r["odds"] if r["result"] == "won" else r["cashout"] or 0) for r in settled)
    return {
        "bets": len(rows),
        "settled": len(settled),
        "wins": wins,
        "losses": losses,
        "stake": stake,
        "returns": returns,
        "net": returns - sum(r["stake"] for r in settled),
        "hit_rate": wins / len(settled) if settled else 0,
    }
