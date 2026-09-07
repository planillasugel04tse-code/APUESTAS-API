from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from .arbitrage import find_arbitrage
from .backtest_report import build_backtest_report
from .dashboard import Period, period_range
from .db import connect
from .market_movement import latest_movements
from .market_performance import performance_by_competition_market
from .providers import provider_status
from .radar import build_radar
from .schemas import BetCreate, BetSettle, MatchCreate, OddsCreate, PickCreate, PickResultCreate, TipsterCreate
from .sync_service import sync_odds

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
        cur = db.execute("INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)", (data.match_id, data.bookmaker, data.market, data.selection, data.odds, captured_at, getattr(data, "line", None)))
        return {"id": cur.lastrowid, **data.model_dump(), "captured_at": captured_at}


@router.post("/picks")
def create_pick(data: PickCreate):
    with connect() as db:
        if not db.execute("SELECT id FROM matches WHERE id = ?", (data.match_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Partido no encontrado")
        if data.tipster_id is not None and not db.execute("SELECT id FROM tipsters WHERE id = ?", (data.tipster_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Tipster no encontrado")
        values = data.model_dump()
        columns = "match_id,tipster_id,original_market,original_selection,original_odds,conservative_market,conservative_selection,conservative_odds,confidence,probability,probability_source,created_at"
        cur = db.execute(f"INSERT INTO picks({columns}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (values["match_id"], values["tipster_id"], values["original_market"], values["original_selection"], values["original_odds"], values["conservative_market"], values["conservative_selection"], values["conservative_odds"], values["confidence"], values["probability"], values["probability_source"], now()))
        return {"id": cur.lastrowid, **values}


@router.post("/picks/{pick_id}/result")
def settle_pick(pick_id: int, data: PickResultCreate, strategy: str = Query(default="original", pattern="^(original|conservative)$")):
    settled_at = data.settled_at or now()
    with connect() as db:
        if not db.execute("SELECT id FROM picks WHERE id = ?", (pick_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Pick no encontrado")
        db.execute("""INSERT INTO pick_strategy_results(pick_id,strategy,result,settled_at,actual_odds,notes) VALUES(?,?,?,?,?,?)
                     ON CONFLICT(pick_id,strategy) DO UPDATE SET result=excluded.result, settled_at=excluded.settled_at, actual_odds=excluded.actual_odds, notes=excluded.notes""", (pick_id, strategy, data.result, settled_at, data.actual_odds, data.notes))
        if strategy == "original":
            db.execute("""INSERT INTO pick_results(pick_id,result,settled_at,actual_odds,notes) VALUES(?,?,?,?,?)
                         ON CONFLICT(pick_id) DO UPDATE SET result=excluded.result, settled_at=excluded.settled_at, actual_odds=excluded.actual_odds, notes=excluded.notes""", (pick_id, data.result, settled_at, data.actual_odds, data.notes))
        return dict(db.execute("SELECT * FROM pick_strategy_results WHERE pick_id=? AND strategy=?", (pick_id, strategy)).fetchone())


@router.get("/tipsters/performance")
def tipsters_performance(period: Period = Query(default=Period.TODOS), market: str | None = None):
    start, end = date_filters(period)
    params: list[object] = []
    clauses = ["pr.result IN ('won','lost','push')"]
    if start: clauses.append("date(pr.settled_at) >= date(?)"); params.append(start)
    if end: clauses.append("date(pr.settled_at) <= date(?)"); params.append(end)
    if market: clauses.append("LOWER(COALESCE(p.conservative_market,p.original_market)) = LOWER(?)"); params.append(market)
    query = f"""SELECT t.id AS tipster_id, t.name, COUNT(*) AS picks, SUM(pr.result='won') AS wins,
                      SUM(pr.result='lost') AS losses, SUM(pr.result='push') AS pushes,
                      AVG(COALESCE(pr.actual_odds,p.conservative_odds,p.original_odds)) AS avg_odds,
                      SUM(CASE WHEN pr.result='won' THEN COALESCE(pr.actual_odds,p.conservative_odds,p.original_odds)-1 WHEN pr.result='lost' THEN -1 ELSE 0 END) AS units
               FROM pick_results pr JOIN picks p ON p.id=pr.pick_id JOIN tipsters t ON t.id=p.tipster_id
               WHERE {' AND '.join(clauses)} GROUP BY t.id,t.name ORDER BY units DESC"""
    with connect() as db: rows = db.execute(query, params).fetchall()
    result = []
    for row in rows:
        picks = row["picks"]; units = row["units"] or 0.0
        result.append({"tipster_id": row["tipster_id"], "name": row["name"], "picks": picks, "wins": row["wins"], "losses": row["losses"], "pushes": row["pushes"], "hit_rate": row["wins"] / picks if picks else 0.0, "avg_odds": row["avg_odds"], "units": units, "roi": units / picks if picks else 0.0, "market": market, "period": period.value})
    return {"period": period.value, "market": market, "tipsters": result}


@router.get("/performance/competition-market")
def competition_market_performance():
    return {"groups": performance_by_competition_market()}


@router.get("/backtest/report")
def backtest_report(period: Period = Query(default=Period.TODOS)):
    return build_backtest_report(period)


@router.get("/bets/summary")
def bets_summary(period: Period = Query(default=Period.TODOS)):
    start, end = date_filters(period)
    with connect() as db:
        query = "SELECT stake, odds, result, cashout, placed_at FROM bets"; params = []; clauses = []
        if start: clauses.append("date(placed_at) >= date(?)"); params.append(start)
        if end: clauses.append("date(placed_at) <= date(?)"); params.append(end)
        if clauses: query += " WHERE " + " AND ".join(clauses)
        rows = db.execute(query, params).fetchall()
    settled = [r for r in rows if r["result"] != "pending"]
    wins = sum(r["result"] == "won" for r in settled); losses = sum(r["result"] == "lost" for r in settled); pushes = sum(r["result"] == "push" for r in settled); cashouts = sum(r["result"] == "cashout" for r in settled)
    stake = sum(r["stake"] for r in settled)
    returns = sum(r["stake"] * r["odds"] if r["result"] == "won" else r["stake"] if r["result"] == "push" else r["cashout"] or 0 for r in settled)
    net = returns - stake
    return {"period": period.value, "from": start, "to": end, "bets": len(rows), "settled": len(settled), "wins": wins, "losses": losses, "pushes": pushes, "cashouts": cashouts, "pending": len(rows)-len(settled), "stake": sum(r["stake"] for r in rows), "settled_stake": stake, "returns": returns, "net": net, "roi": net/stake if stake else 0, "hit_rate": wins/len(settled) if settled else 0}


@router.get("/opportunities")
def opportunities(limit: int = Query(default=20, ge=1, le=100)):
    return build_radar(limit=limit)


@router.get("/arbitrage")
def arbitrage(limit: int = Query(default=100, ge=1, le=500)):
    return {"opportunities": [item.__dict__ for item in find_arbitrage(limit)]}


@router.get("/providers")
def providers():
    return {"providers": provider_status()}


@router.post("/sync/odds")
async def sync_odds_endpoint(bookmakers: str = Query(default="Betano"), include_live: bool = False, limit_per_league: int = Query(default=100, ge=1, le=200)):
    books = [item.strip() for item in bookmakers.split(",") if item.strip()]
    if not books:
        raise HTTPException(status_code=400, detail="Debes indicar al menos una casa de apuestas")
    summary = await sync_odds(books, include_live=include_live, limit_per_league=limit_per_league)
    return summary.__dict__


@router.get("/movements")
def movements(match_id: int | None = None):
    return {"movements": [item.__dict__ for item in latest_movements(match_id)]}


@router.get("/dashboard/periods")
def dashboard_periods():
    return {"periods": [{"id":"hoy","label":"HOY"},{"id":"lunes-viernes","label":"LUNES A VIERNES"},{"id":"sabado-domingo","label":"SÁBADO DOMINGO"},{"id":"mes","label":"MES"},{"id":"3-meses","label":"3 MESES"},{"id":"6-meses","label":"6 MESES"},{"id":"todos","label":"TODOS"}]}
