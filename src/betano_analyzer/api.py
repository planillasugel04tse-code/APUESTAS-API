from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from .dashboard import Period, period_range
from .db import connect
from .providers import provider_status
from .radar import build_radar
from .schemas import BetCreate, BetSettle, MatchCreate, OddsCreate, PickCreate, TipsterCreate

router = APIRouter(prefix="/api/v1")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def date_filters(period: Period):
    start, end = period_range(period)
    return start.isoformat() if start else None, end.isoformat() if end else None


@router.post("/matches")
def create_match(data: MatchCreate):
    with connect() as db:
        cur = db.execute("INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)", (data.external_id, data.competition, data.home_team, data.away_team, data.kickoff, data.status))
        return {"id": cur.lastrowid, **data.model_dump()}


@router.post("/tipsters")
def create_tipster(data: TipsterCreate):
    with connect() as db:
        if db.execute("SELECT id FROM tipsters WHERE name = ?", (data.name,)).fetchone():
            raise HTTPException(status_code=409, detail="El tipster ya existe")
        cur = db.execute("INSERT INTO tipsters(name,source,country,language,active) VALUES(?,?,?,?,?)", (data.name, data.source, data.country, data.language, int(data.active)))
        return {"id": cur.lastrowid, **data.model_dump()}


@router.post("/odds")
def create_odds(data: OddsCreate):
    captured_at = data.captured_at or now()
    with connect() as db:
        if not db.execute("SELECT id FROM matches WHERE id = ?", (data.match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        cur = db.execute("INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at) VALUES(?,?,?,?,?,?)", (data.match_id, data.bookmaker, data.market, data.selection, data.odds, captured_at))
        return {"id": cur.lastrowid, **data.model_dump(), "captured_at": captured_at}


@router.post("/picks")
def create_pick(data: PickCreate):
    with connect() as db:
        if not db.execute("SELECT id FROM matches WHERE id = ?", (data.match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        if data.tipster_id is not None and not db.execute("SELECT id FROM tipsters WHERE id = ?", (data.tipster_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Tipster no encontrado")
        cur = db.execute("""INSERT INTO picks(match_id,tipster_id,original_market,original_selection,original_odds,conservative_market,conservative_selection,conservative_odds,confidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""", (*data.model_dump().values(), now()))
        return {"id": cur.lastrowid, **data.model_dump()}


@router.post("/bets")
def create_bet(data: BetCreate):
    with connect() as db:
        if not db.execute("SELECT id FROM matches WHERE id = ?", (data.match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        if data.pick_id is not None and not db.execute("SELECT id FROM picks WHERE id = ?", (data.pick_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Pick no encontrado")
        if data.result == "cashout" and data.cashout is None:
            raise HTTPException(status_code=422, detail="Una apuesta cashout requiere importe de cashout")
        cur = db.execute("INSERT INTO bets(match_id,pick_id,selection,odds,stake,result,cashout,placed_at) VALUES(?,?,?,?,?,?,?,?)", (*data.model_dump().values(),))
        return {"id": cur.lastrowid, **data.model_dump(), "potential_return": data.stake * data.odds}


@router.patch("/bets/{bet_id}/settle")
def settle_bet(bet_id: int, data: BetSettle):
    if data.result == "cashout" and data.cashout is None:
        raise HTTPException(status_code=422, detail="Una apuesta cashout requiere importe de cashout")
    settled_at = data.settled_at or now()
    with connect() as db:
        cur = db.execute("UPDATE bets SET result = ?, cashout = ?, settled_at = ? WHERE id = ?", (data.result, data.cashout, settled_at, bet_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Apuesta no encontrada")
        return dict(db.execute("SELECT * FROM bets WHERE id = ?", (bet_id,)).fetchone())


@router.get("/bets/summary")
def bets_summary(period: Period = Query(default=Period.TODOS)):
    start, end = date_filters(period)
    with connect() as db:
        query = "SELECT stake, odds, result, cashout, placed_at FROM bets"
        params = []
        clauses = []
        if start:
            clauses.append("date(placed_at) >= date(?)"); params.append(start)
        if end:
            clauses.append("date(placed_at) <= date(?)"); params.append(end)
        if clauses: query += " WHERE " + " AND ".join(clauses)
        rows = db.execute(query, params).fetchall()
    settled = [r for r in rows if r["result"] != "pending"]
    wins = sum(r["result"] == "won" for r in settled)
    losses = sum(r["result"] == "lost" for r in settled)
    pushes = sum(r["result"] == "push" for r in settled)
    cashouts = sum(r["result"] == "cashout" for r in settled)
    stake = sum(r["stake"] for r in settled)
    returns = sum(r["stake"] * r["odds"] if r["result"] == "won" else r["stake"] if r["result"] == "push" else r["cashout"] or 0 for r in settled)
    net = returns - stake
    return {"period": period.value, "from": start, "to": end, "bets": len(rows), "settled": len(settled), "wins": wins, "losses": losses, "pushes": pushes, "cashouts": cashouts, "pending": len(rows) - len(settled), "stake": sum(r["stake"] for r in rows), "settled_stake": stake, "returns": returns, "net": net, "roi": net / stake if stake else 0, "hit_rate": wins / len(settled) if settled else 0}


@router.get("/opportunities")
def opportunities(limit: int = Query(default=20, ge=1, le=100)):
    return build_radar(limit=limit)


@router.get("/providers")
def providers():
    return {"providers": provider_status()}


@router.get("/dashboard/periods")
def dashboard_periods():
    return {"periods": [{"id": "hoy", "label": "HOY"}, {"id": "lunes-viernes", "label": "LUNES A VIERNES"}, {"id": "sabado-domingo", "label": "SÁBADO Y DOMINGO"}, {"id": "mes", "label": "MES"}, {"id": "3-meses", "label": "3 MESES"}, {"id": "6-meses", "label": "6 MESES"}, {"id": "todos", "label": "TODOS"}]}
