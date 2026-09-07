from __future__ import annotations

from pathlib import Path

from .calibration import calibration_report
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


def _probability_quality(rows: list[dict]) -> dict:
    """Measure historical probability quality without treating pushes as binary outcomes."""
    settled = [
        row for row in rows
        if row.get("probability") is not None and row["result"] in {"won", "lost"}
    ]
    if not settled:
        return {
            "samples": 0,
            "available": False,
            "reason": "no_settled_binary_probability_samples",
        }

    probabilities = [float(row["probability"]) for row in settled]
    outcomes = [1 if row["result"] == "won" else 0 for row in settled]
    report = calibration_report(probabilities, outcomes)
    return {
        "available": True,
        "samples": report.samples,
        "brier_score": report.brier_score,
        "log_loss": report.log_loss,
        "mean_probability": report.mean_probability,
        "observed_rate": report.observed_rate,
        "mean_absolute_error": report.mean_absolute_error,
        "calibration_error": report.calibration_error,
        "buckets": list(report.buckets),
    }


def _probability_quality_by_source(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        source = row.get("probability_source") or "sin_fuente"
        groups.setdefault(source, []).append(row)
    out = []
    for source, values in groups.items():
        quality = _probability_quality(values)
        out.append({"probability_source": source, **quality})
    return sorted(out, key=lambda x: (x["samples"] >= 30, x["samples"]), reverse=True)


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
            SELECT m.competition, p.pick_id,
                   pk.original_market, pk.original_odds,
                   pk.conservative_market, pk.conservative_odds,
                   pk.probability, pk.probability_source,
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

    probability_rows = original_rows
    return {
        "period": period.value,
        "overall": {"original": _summary(original_rows), "conservative": _summary(conservative_rows), "actual": _actual_summary(actual_records)},
        "probability_quality": _probability_quality(probability_rows),
        "probability_quality_by_source": _probability_quality_by_source(probability_rows),
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
            "probability_samples": len([r for r in probability_rows if r.get("probability") is not None and r["result"] in {"won", "lost"}]),
        },
        "note": "Original, conservadora y apuesta real se miden por separado. La estrategia real usa las apuestas registradas y no replica resultados faltantes. La calidad de probabilidades se calcula solo con resultados binarios liquidados (won/lost); push no se fuerza a 0/1."
    }
