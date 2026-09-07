from __future__ import annotations

from fastapi import APIRouter, Query

from .model_engine import elo_probabilities, monte_carlo_poisson
from .model_baseline import poisson_baseline

router = APIRouter(prefix="/api/v1/model", tags=["model"])


@router.get("/poisson")
def poisson(home_goals: float = Query(gt=0), away_goals: float = Query(gt=0), max_goals: int = Query(default=12, ge=6, le=30)):
    result = poisson_baseline(home_goals, away_goals, max_goals=max_goals)
    return result.__dict__


@router.get("/elo")
def elo(home_rating: float = 1500.0, away_rating: float = 1500.0, home_advantage: float = 55.0, draw_probability: float = Query(default=0.27, gt=0, lt=1)):
    home, draw, away = elo_probabilities(home_rating, away_rating, home_advantage, draw_probability)
    return {"home_win": home, "draw": draw, "away_win": away, "fair_home": 1 / home, "fair_draw": 1 / draw, "fair_away": 1 / away}


@router.get("/monte-carlo")
def monte_carlo(home_goals: float = Query(gt=0), away_goals: float = Query(gt=0), simulations: int = Query(default=100000, ge=1000, le=1000000), seed: int = 42):
    result = monte_carlo_poisson(home_goals, away_goals, simulations=simulations, seed=seed)
    return result.__dict__
