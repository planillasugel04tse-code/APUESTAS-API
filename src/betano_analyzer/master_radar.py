from __future__ import annotations

from collections import defaultdict

from .db import connect
from .radar_value import build_value_radar
from .radar import build_radar


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def build_master_radar(limit: int = 20) -> dict:
    """Combine value, model/radar, market movement and stored history.

    The score ranks evidence; it is not a win probability.
    """
    value = build_value_radar(limit=100, offered_bookmaker="Betano")
    base = build_radar(limit=100)
    base_items = base.get("opportunities", []) if isinstance(base, dict) else []
    value_items = value.get("opportunities", []) if isinstance(value, dict) else []

    by_key: dict[tuple, dict] = {}
    for item in base_items:
        key = (item.get("match_id"), str(item.get("market", "")).lower(), str(item.get("selection", "")).lower(), item.get("line"))
        by_key[key] = item
    value_by_key: dict[tuple, dict] = {}
    for item in value_items:
        key = (item.get("match_id"), str(item.get("market", "")).lower(), str(item.get("selection", "")).lower(), item.get("line"))
        value_by_key[key] = item

    match_ids = {key[0] for key in value_by_key}
    movement: dict[int, float] = defaultdict(float)
    history: dict[tuple, float] = {}
    with connect() as db:
        if match_ids:
            placeholders = ",".join("?" for _ in match_ids)
            rows = db.execute(f"SELECT match_id, market, selection, line, odds, captured_at FROM odds WHERE match_id IN ({placeholders}) ORDER BY captured_at", list(match_ids)).fetchall()
            previous: dict[tuple, float] = {}
            for row in rows:
                key = (row["match_id"], str(row["market"]).lower(), str(row["selection"]).lower(), row["line"])
                old = previous.get(key)
                if old and old > 0:
                    movement[row["match_id"]] = max(movement[row["match_id"]], float(row["odds"]) / old - 1)
                previous[key] = float(row["odds"])
        history_rows = db.execute("""SELECT p.match_id, COALESCE(p.conservative_market,p.original_market) AS market, COALESCE(p.conservative_selection,p.original_selection) AS selection, SUM(pr.result='won') AS wins, COUNT(*) AS total FROM pick_results pr JOIN picks p ON p.id=pr.pick_id WHERE pr.result IN ('won','lost','push') GROUP BY p.match_id, market, selection""").fetchall()
        for row in history_rows:
            history[(row["match_id"], str(row["market"]).lower(), str(row["selection"]).lower())] = (row["wins"] or 0) / row["total"] if row["total"] else 0.0

    candidates = []
    for key, v in value_by_key.items():
        b = by_key.get(key, {})
        edge = float(v.get("edge", 0.0) or 0.0)
        ev = float(v.get("ev", 0.0) or 0.0)
        consensus = int(v.get("bookmakers", 0) or 0)
        model_edge = float(b.get("edge", 0.0) or 0.0)
        model_conf = float(b.get("confidence", 0.0) or 0.0)
        move = movement.get(key[0], 0.0)
        hist = history.get((key[0], key[1], key[2]), 0.0)
        score = 35 + _clamp(edge * 250, -10, 25) + _clamp(ev * 100, -5, 15) + min(consensus, 6) * 2
        score += _clamp(model_edge * 120, -8, 12) + _clamp(model_conf * 12, 0, 12) + _clamp(move * 80, -5, 5)
        if hist:
            score += _clamp((hist - 0.5) * 20, -6, 6)
        rating = "fuerte" if score >= 80 else "interesante" if score >= 68 else "vigilar" if score >= 55 else "descartar"
        candidates.append({**v, "master_score": round(_clamp(score), 1), "rating": rating, "model_edge": round(model_edge, 4), "model_confidence": round(model_conf, 4), "movement": round(move, 4), "historical_hit_rate": round(hist, 4), "signals": {"value": edge >= 0.03, "consensus": consensus >= 3, "model": model_edge > 0, "movement": move > 0, "history": hist >= 0.55}})

    candidates.sort(key=lambda x: (x["master_score"], x["edge"], x["bookmakers"]), reverse=True)
    return {"count": min(limit, len(candidates)), "method": "value + radar + movement + historical results", "warning": "master_score es un ranking de señales, no una probabilidad de acierto ni una garantía de beneficio.", "opportunities": candidates[: max(1, min(limit, 100))]}
