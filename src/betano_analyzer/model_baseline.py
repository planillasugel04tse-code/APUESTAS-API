from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial


@dataclass(frozen=True)
class PoissonBaseline:
    home_goals: float
    away_goals: float
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    btts_yes: float


def _poisson_pmf(lam: float, goals: int) -> float:
    if lam < 0 or goals < 0:
        raise ValueError("lambda y goles deben ser no negativos")
    return exp(-lam) * lam**goals / factorial(goals)


def poisson_baseline(home_goals: float, away_goals: float, max_goals: int = 12) -> PoissonBaseline:
    if home_goals <= 0 or away_goals <= 0:
        raise ValueError("Los goles esperados deben ser mayores que 0")
    if max_goals < 6 or max_goals > 30:
        raise ValueError("max_goals debe estar entre 6 y 30")

    home = [_poisson_pmf(home_goals, i) for i in range(max_goals + 1)]
    away = [_poisson_pmf(away_goals, i) for i in range(max_goals + 1)]
    total = sum(home) * sum(away)
    home_win = sum(home[i] * away[j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i > j) / total
    draw = sum(home[i] * away[i] for i in range(max_goals + 1)) / total
    away_win = sum(home[i] * away[j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i < j) / total
    over_2_5 = sum(home[i] * away[j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i + j >= 3) / total
    btts_yes = sum(home[i] * away[j] for i in range(1, max_goals + 1) for j in range(1, max_goals + 1)) / total
    return PoissonBaseline(home_goals, away_goals, home_win, draw, away_win, over_2_5, btts_yes)
