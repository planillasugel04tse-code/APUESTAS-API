from __future__ import annotations

from .db import connect
from .dashboard import Period, period_range


def _summary(rows: list[dict], odds_key: str) -> dict:
    settled = [r for r in rows if r["result"] in {"won", "lost", "push"} and r[odds_key] and r[odds_key] > 1]
    wins = sum(r["result"] == "won" for r in settled)
    losses = sum(r["result"] == "lost" for r in settled)
    pushes = sum(r["result"] == "push" for r in settled)
    stake = float(len(settled))
    returns = sum((r[odds_key] if r["result"] == "won" else 1.0 if r["result"] == "push" else 0.0) for r in settled)
    net = returns - stake
    return {"bets": len(settled), "wins": wins, "losses": losses, "pushes": pushes,
            "hit_rate": wins / len(settled) if settled else 0.0,
            "stake_units": stake, "returns_units": returns, "net_units": net,
            "roi": net / stake if stake else 0.0}


def build_backtest_report(period: Period = Period.TODOS) -> dict:
    start, end = period_range(period)
    clauses = ["pr.result IN ('won','lost','push')"]
    params: list[object] = []
    if start:
        clauses.append("date(pr.settled_at) >= date(?)")
        params.append(start.isoformat())
    if end:
        clauses.append("date(pr.settled_at) <= date(?)")
        params.append(end.isoformat())
    with connect() as db:
        rows = db.execute(f"""SELECT m.competition, p.original_market, p.original_odds,
                                     p.conservative_market, p.conservative_odds, pr.result, pr.actual_odds
                              FROM pick_results pr JOIN picks p ON p.id=pr.pick_id
                              JOIN matches m ON m.id=p.match_id
                              WHERE {' AND '.join(clauses)}""", params).fetchall()
    records = [dict(r) for r in rows]
    original_rows = [{**r, "odds": r["original_odds"]} for r in records]
    conservative_rows = [{**r, "odds": r["conservative_odds"]} for r in records]

    def grouped(source: list[dict], odds_field: str) -> list[dict]:
        groups: dict[tuple[str, str], list[dict]] = {}
        for r in source:
            market = r["original_market"] if odds_field == "original_odds" else r["conservative_market"]
            groups.setdefault((r["competition"] or "Sin competición", market or "Sin mercado"), []).append(r)
        out = []
        for (competition, market), values in groups.items():
            out.append({"competition": competition, "market": market, **_summary(values, odds_field)})
        return sorted(out, key=lambda x: (x["bets"] >= 30, x["roi"]), reverse=True)

    return {"period": period.value,
            "overall": {"original": _summary(original_rows, "original_odds"),
                        "conservative": _summary(conservative_rows, "conservative_odds")},
            "by_competition_market": {"original": grouped(original_rows, "original_odds"),
                                      "conservative": grouped(conservative_rows, "conservative_odds")},
            "note": "La comparación usa la misma muestra histórica. Para validar una transformación conservadora de verdad, el resultado registrado debe corresponder a esa selección; no se inventa un resultado alternativo."}
