from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class EloTeam:
    rating: float = 1500.0


def elo_expected(home_rating: float, away_rating: float, home_advantage: float = 55.0) -> float:
    """Probability of a home win from an Elo difference."""
    diff = (home_rating + home_advantage) - away_rating
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def update_elo(home_rating: float, away_rating: float, home_goals: int, away_goals: int,
              k: float = 20.0, home_advantage: float = 55.0) -> tuple[float, float]:
    if home_goals < 0 or away_goals < 0:
        raise ValueError("Los goles no pueden ser negativos")
    if k <= 0:
        raise ValueError("k debe ser positivo")
    expected_home = elo_expected(home_rating, away_rating, home_advantage)
    if home_goals > away_goals:
        score_home = 1.0
    elif home_goals == away_goals:
        score_home = 0.5
    else:
        score_home = 0.0
    margin = max(1.0, math.log(abs(home_goals - away_goals) + 1.0) + 1.0)
    delta = k * margin * (score_home - expected_home)
    return home_rating + delta, away_rating - delta


def elo_probabilities(home_rating: float, away_rating: float, home_advantage: float = 55.0,
                      draw_probability: float = 0.27) -> tuple[float, float, float]:
    """Return a simple Elo 1X2 prior; draw is an explicit prior, not fitted data."""
    if not 0 < draw_probability < 1:
        raise ValueError("draw_probability debe estar entre 0 y 1")
    home = elo_expected(home_rating, away_rating, home_advantage)
    draw = draw_probability
    home = home * (1.0 - draw)
    away = (1.0 - draw) - home
    return home, draw, away


@dataclass(frozen=True)
class SimulationResult:
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    btts_yes: float


def monte_carlo_poisson(home_goals: float, away_goals: float, simulations: int = 100_000,
                        seed: int = 42) -> SimulationResult:
    """Monte Carlo market probabilities using independent Poisson goal rates."""
    if home_goals <= 0 or away_goals <= 0:
        raise ValueError("Las medias de goles deben ser positivas")
    if simulations < 1_000:
        raise ValueError("simulations debe ser >= 1000")
    rng = random.Random(seed)
    home_wins = draws = away_wins = overs = btts = 0
    for _ in range(simulations):
        h = rng.poisson(home_goals) if hasattr(rng, "poisson") else _sample_poisson(rng, home_goals)
        a = rng.poisson(away_goals) if hasattr(rng, "poisson") else _sample_poisson(rng, away_goals)
        if h > a:
            home_wins += 1
        elif h == a:
            draws += 1
        else:
            away_wins += 1
        if h + a >= 3:
            overs += 1
        if h > 0 and a > 0:
            btts += 1
    n = float(simulations)
    return SimulationResult(home_wins / n, draws / n, away_wins / n, overs / n, btts / n)


def _sample_poisson(rng: random.Random, lam: float) -> int:
    limit = math.exp(-lam)
    product = 1.0
    k = 0
    while product > limit:
        k += 1
        product *= rng.random()
    return k - 1
