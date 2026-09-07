import pytest

from betano_analyzer.model_engine import (
    elo_expected,
    elo_probabilities,
    monte_carlo_poisson,
    update_elo,
)


def test_elo_equal_teams_has_home_advantage():
    p = elo_expected(1500, 1500)
    assert 0.5 < p < 0.6


def test_elo_update_moves_ratings_after_home_win():
    home, away = update_elo(1500, 1500, 2, 0)
    assert home > 1500
    assert away < 1500


def test_elo_probabilities_sum_to_one():
    probs = elo_probabilities(1550, 1500)
    assert sum(probs) == pytest.approx(1.0)
    assert all(0 < p < 1 for p in probs)


def test_monte_carlo_is_reproducible_and_valid():
    result_a = monte_carlo_poisson(1.4, 1.1, simulations=5000, seed=7)
    result_b = monte_carlo_poisson(1.4, 1.1, simulations=5000, seed=7)
    assert result_a == result_b
    assert result_a.home_win + result_a.draw + result_a.away_win == pytest.approx(1.0)
    assert 0 < result_a.over_2_5 < 1
    assert 0 < result_a.btts_yes < 1


def test_model_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        elo_probabilities(1500, 1500, draw_probability=1.0)
    with pytest.raises(ValueError):
        monte_carlo_poisson(0, 1.0)
