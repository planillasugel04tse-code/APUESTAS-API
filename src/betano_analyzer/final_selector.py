from __future__ import annotations

from .master_radar import build_master_radar


def build_final_selection(limit: int = 10) -> dict:
    radar = build_master_radar(limit=100)
    candidates = radar.get("opportunities", [])
    selected: list[dict] = []

    for item in candidates:
        score = float(item.get("master_score", 0))
        edge = float(item.get("edge", 0))
        ev = float(item.get("ev", 0))
        books = int(item.get("bookmakers", 0))
        signals = item.get("signals", {})
        positive = sum(bool(v) for v in signals.values())

        if score < 68 or edge < 0.03 or ev < 0.03:
            continue
        if books < 2:
            continue
        if positive < 2:
            continue

        action = "APOSTAR" if score >= 80 and edge >= 0.05 and ev >= 0.05 else "VIGILAR"
        selected.append({
            **item,
            "action": action,
            "selection_reason": {
                "master_score": score,
                "edge": edge,
                "ev": ev,
                "bookmakers": books,
                "positive_signals": positive,
            },
        })

    selected.sort(key=lambda x: (x["master_score"], x["edge"], x["ev"]), reverse=True)
    selected = selected[: max(1, min(limit, 10))]

    return {
        "count": len(selected),
        "requested": min(limit, 10),
        "status": "OK" if selected else "NO_BET",
        "note": "No se rellenan cupos con selecciones débiles. Si no hay suficientes candidatos, se devuelve menos de 10.",
        "opportunities": selected,
    }
