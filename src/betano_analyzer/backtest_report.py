from __future__ import annotations

from pathlib import Path

from .db import connect
from .dashboard import Period, period_range


def _summary(rows: list[dict]) -> dict:
    settled = [r for r in rows if r["result"] in {"won", "lost", "push"} and r.get("odds") and r["odds"] > 1]
    wins = sum(r["result"] == "won" for r in settled)
    losses = sum(r["result"] == "lost" for r in settled)
    pushes = sum(r["result"] == "push" for r in settled)
    stake = float(len(settled))
    returns = sum((r["odds"] if r["result"] == "won" else 1.0 if r["result"] == "push" else 0.0) for r in settled)
    net = returns - stake
    return {"bets": len(settled), "wins": wins, "losses": losses, "pushes": pushes,
            "hit_rate": wins / len(settled) if settled else 0.0,
            "stake_units": stake, "returns_units": returns, "net_units": net,
            "roi": net / stake if stake else 0.0}


def _actual_summary(rows: list[dict]) -> dict:
    settled = [r for r in rows if r["result"] in {"won", "lost", "push", "cashout"} and r.get("odds") and r["odds"] > 1]
    wins = sum(r["result"] == "won" for r in settled)
    losses = sum(r["result"] == "lost" for r in settled)
    pushes = sum(r["result"] == "push" for r in settled)
    cashouts = sum(r["result"] == "cashout" for r in settled)
    stake = sum(float(r["stake"]) for r in settled)
    returns = sum(
        float(r["stake"]) * float(r["odds"]) if r["result"] == "won"
        else float(r["stake"]) if r["result"] == "push"
        else float(r.get("cashout") or 0) if r["result"] == "cashout" else 0.0
        for r in settled
    )
    net = returns - stake
    return {"bets": len(settled), "wins": wins, "losses": losses, "pushes": pushes, "cashouts": cashouts,
            "hit_rate": wins / len(settled) if settled else 0.0,
            "stake": stake, "returns": returns, "net": net, "roi": net / stake if stake else 0.0}


def _grouped(rows: list[dict], market_key: str) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["competition"] or "Sin competición", row.get(market_key) or "Sin mercado"), []).append(row)
    out = []
    for (competition, market), values in groups.items():
        out.append({"competition": competition, "market": market, **_summary(values)})
    return sorted(out, key=lambda x: (x["bets"] >= 30, x["roi"]), reverse=True)


def _grouped_actual(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["competition"] or "Sin competición", row.get("market") or "apuesta_real"), []).append(row)
    out = []
    for (competition, market), values in groups.items():
        out.append({"competition": competition, "market": market, **_actual_summary(values)})
    return sorted(out, key=lambda x: (x["bets"] >= 30, x["roi"]), reverse=True)


def build_backtest_report(period: Period = Period.TODOS, db_path: str | Path | None = None) -> dict:
    start, end = period_range(period)
    clauses = ["p.result IN ('won','lost','push')"]
    bet_clauses = ["b.result IN ('won','lost','push','cashout')"]
    params: list[object] = []
    bet_params: list[object] = []
    if start:
        clauses.append("date(p.settled_at) >= date(?)")
        params.append(start.isoformat())
        bet_clauses.append("date(COALESCE(b.settled_at,b.placed_at)) >= date(?)")
        bet_params.append(start.isoformat())
    if end:
        clauses.append("date(p.settled_at) <= date(?)")
        params.append(end.isoformat())
        bet_clauses.append("date(COALESCE(b.settled_at,b.placed_at)) <= date(?)")
        bet_params.append(end.isoformat())

    with connect(db_path or "betano_analyzer.sqlite3") as db:
        rows = db.execute(f"""
            SELECT m.competition, p.id AS pick_id,
                   pk.original_market, pk.original_odds,
                   pk.conservative_market, pk.conservative_odds,
                   p.strategy, p.result, p.actual_odds
            FROM pick_strategy_results p
            JOIN picks pk ON pk.id=p.pick_id
            JOIN matches m ON m.id=pk.match_id
            WHERE {' AND '.join(clauses)}
        """, params).fetchall()
        bet_rows = db.execute(f"""
            SELECT m.competition,
                   COALESCE(p.original_market, 'apuesta_real') AS market,
                   b.id AS bet_id, b.stake, b.odds, b.result, b.cashout
            FROM bets b
            JOIN matches m ON m.id=b.match_id
            LEFT JOIN picks p ON p.id=b.pick_id
            WHERE {' AND '.join(bet_clauses)}
        """, bet_params).fetchall()

    records = [dict(r) for r in rows]
    actual_records = [dict(r) for r in bet_rows]
    original_rows = []
    conservative_rows = []
    for row in records:
        if row["strategy"] == "original":
            original_rows.append({**row, "odds": row["actual_odds"] or row["original_odds"]})
        elif row["strategy"] == "conservative":
            conservative_rows.append({**row, "odds": row["actual_odds"] or row["conservative_odds"]})

    return {
        "period": period.value,
        "overall": {"original": _summary(original_rows), "conservative": _summary(conservative_rows), "actual": _actual_summary(actual_records)},
        "by_competition_market": {
            "original": _grouped(original_rows, "original_market"),
            "conservative": _grouped(conservative_rows, "conservative_market"),
            "actual": _grouped_actual(actual_records),
        },
        "coverage": {
            "original_picks": len(original_rows),
            "conservative_picks": len(conservative_rows),
            "paired_picks": len({r["pick_id"] for r in original_rows} & {r["pick_id"] for r in conservative_rows}),
            "actual_bets": len(actual_records),
        },
        "note": "Original, conservadora y apuesta real se miden por separado. La estrategia real usa las apuestas registradas y no replica resultados faltantes."
    }
