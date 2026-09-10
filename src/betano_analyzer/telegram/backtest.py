from __future__ import annotations

from ..backtest import BacktestRow, evaluate
from ..db import connect


def evaluate_telegram_backtest(*, tipster: str | None = None, channel: str | None = None) -> dict:
    """Feed settled Telegram picks into the existing core backtest engine."""
    clauses = ["ts.match_status='matched'", "pr.result IN ('won','lost','push')"]
    params: list[object] = []
    if tipster:
        clauses.append("ts.tipster=?")
        params.append(tipster)
    if channel:
        clauses.append("ts.channel=?")
        params.append(channel)

    with connect() as db:
        rows = db.execute(
            f"""SELECT ts.tipster_odds, pr.result
                FROM telegram_signals ts
                JOIN picks p ON p.match_id=ts.matched_event_id
                             AND LOWER(p.original_market)=LOWER(ts.market)
                             AND LOWER(p.original_selection)=LOWER(ts.selection)
                             AND ABS(COALESCE(p.original_odds,0)-COALESCE(ts.tipster_odds,0)) < 0.0001
                JOIN pick_results pr ON pr.pick_id=p.id
                WHERE {' AND '.join(clauses)}
                ORDER BY pr.settled_at""",
            params,
        ).fetchall()

    backtest_rows = [BacktestRow(result=str(row["result"]), odds=float(row["tipster_odds"]), stake=1.0) for row in rows if row["tipster_odds"] and float(row["tipster_odds"]) > 1]
    result = evaluate(backtest_rows)
    return {"source": "telegram", "engine": "betano_analyzer.backtest.evaluate", **result}
