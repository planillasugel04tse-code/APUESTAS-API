from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TipsterScore:
    tipster_id: int
    name: str
    picks: int
    wins: int
    hit_rate: float
    roi: float
    avg_odds: float
    score: float
    tier: str


def score_tipster(*, tipster_id: int, name: str, picks: int, wins: int,
                  roi: float, avg_odds: float) -> TipsterScore:
    hit_rate = wins / picks if picks else 0.0
    # Volume is deliberately capped so a tiny hot streak cannot dominate.
    volume_factor = min(picks / 100.0, 1.0)
    roi_component = max(-1.0, min(1.0, roi))
    hit_component = max(0.0, min(1.0, (hit_rate - 0.50) / 0.30))
    score = (0.50 * roi_component + 0.35 * hit_component + 0.15 * volume_factor)
    if picks < 30:
        tier = "insuficiente"
    elif score >= 0.45:
        tier = "elite"
    elif score >= 0.25:
        tier = "fuerte"
    elif score >= 0.10:
        tier = "vigilar"
    else:
        tier = "descartar"
    return TipsterScore(
        tipster_id=tipster_id,
        name=name,
        picks=picks,
        wins=wins,
        hit_rate=hit_rate,
        roi=roi,
        avg_odds=avg_odds,
        score=score,
        tier=tier,
    )
