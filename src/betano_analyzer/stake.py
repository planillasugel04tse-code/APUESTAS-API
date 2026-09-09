from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class StakeAllocation:
    total_stake: float
    implied_sum: float
    guaranteed_return: float
    guaranteed_profit: float
    profit_margin: float
    stakes: dict[str, float]


def allocate_stakes(outcomes: dict[str, float], total_stake: float) -> StakeAllocation:
    """Allocate a total stake across a true arbitrage opportunity.

    Stakes are proportional to inverse odds, making the gross return the same
    for every outcome. The function refuses invalid odds, non-positive stakes,
    or combinations that are not actually arbitrage opportunities.
    """
    if not isfinite(total_stake) or total_stake <= 0:
        raise ValueError("total_stake debe ser mayor que 0")
    if not outcomes:
        raise ValueError("outcomes no puede estar vacío")

    clean = {str(k): float(v) for k, v in outcomes.items()}
    if any(not isfinite(v) or v <= 1.0 for v in clean.values()):
        raise ValueError("todas las cuotas deben ser mayores que 1")

    implied_sum = sum(1.0 / odds for odds in clean.values())
    if implied_sum >= 1.0:
        raise ValueError("las cuotas no forman una surebet")

    guaranteed_return = total_stake / implied_sum
    stakes = {key: total_stake * (1.0 / odds) / implied_sum for key, odds in clean.items()}
    guaranteed_profit = guaranteed_return - total_stake
    return StakeAllocation(
        total_stake=total_stake,
        implied_sum=implied_sum,
        guaranteed_return=guaranteed_return,
        guaranteed_profit=guaranteed_profit,
        profit_margin=guaranteed_profit / total_stake,
        stakes=stakes,
    )
