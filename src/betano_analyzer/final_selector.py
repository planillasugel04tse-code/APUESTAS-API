from __future__ import annotations

from .master_radar import build_master_radar


def _rejection_reason(
    score: float,
    edge: float,
    ev: float,
    probability: float,
    has_fusion: bool,
    books: int,
    positive: int,
) -> str:
    """Explain why an opportunity was not selected, in priority order."""
    reasons = []
    if score < 68:
        reasons.append(f"master_score {score:.1f} < 68")
    if edge < 0.03:
        reasons.append(f"edge {edge:.4f} < 0.03")
    if ev < 0.03:
        reasons.append(f"ev {ev:.4f} < 0.03")
    if has_fusion and probability < 0.50:
        reasons.append(f"fused_probability {probability:.4f} < 0.50")
    if books < 2:
        reasons.append(f"bookmakers {books} < 2")
    if positive < 2:
        reasons.append(f"positive_signals {positive} < 2")
    return "; ".join(reasons) if reasons else "unknown"


def build_final_selection(limit: int = 10) -> dict:
    """Select the strongest opportunities from Master Radar.

    Each rejected opportunity includes a ``rejection_reason`` field explaining
    why it did not qualify, so callers can diagnose the filtering logic.
    """
    radar = build_master_radar(limit=100)
    candidates = radar.get("opportunities", [])
    selected: list[dict] = []
    rejected: list[dict] = []

    for item in candidates:
        score = float(item.get("master_score", 0))
        has_fusion = "fused_probability" in item
        probability = float(item.get("fused_probability", item.get("model_probability", 0)) or 0)
        edge = float(item.get("fused_edge", item.get("edge", 0)) or 0)
        ev = float(item.get("fused_ev", item.get("ev", 0)) or 0)
        books = int(item.get("bookmakers", 0))
        signals = item.get("signals", {})
        positive = sum(bool(v) for v in signals.values())

        passes = (
            score >= 68
            and edge >= 0.03
            and ev >= 0.03
            and (not has_fusion or probability >= 0.50)
            and books >= 2
            and positive >= 2
        )

        if not passes:
            rejected.append({
                **item,
                "rejection_reason": _rejection_reason(score, edge, ev, probability, has_fusion, books, positive),
                "action": "DESCARTADO",
            })
            continue

        action = "APOSTAR" if score >= 80 and edge >= 0.05 and ev >= 0.05 else "VIGILAR"
        selected.append({
            **item,
            "action": action,
            "rejection_reason": None,
            "selection_reason": {
                "master_score": score,
                "fused_probability": probability,
                "fused_edge": edge,
                "fused_ev": ev,
                "bookmakers": books,
                "positive_signals": positive,
            },
        })

    selected.sort(
        key=lambda x: (x["master_score"], x.get("fused_edge", 0), x.get("fused_ev", 0)),
        reverse=True,
    )
    selected = selected[: max(1, min(limit, 10))]

    return {
        "count": len(selected),
        "requested": min(limit, 10),
        "status": "OK" if selected else "NO_BET",
        "note": (
            "La selección final exige valor de la probabilidad fusionada cuando está disponible, "
            "consenso y señales positivas; no se rellenan cupos con selecciones débiles. "
            "El campo rejection_reason explica por qué cada oportunidad fue descartada."
        ),
        "opportunities": selected,
        "rejected_count": len(rejected),
        "rejected": rejected,
    }
