import pytest

from betano_analyzer.model_baseline import poisson_baseline


def test_poisson_baseline_probabilities_are_valid():
    result = poisson_baseline(1.5, 1.1)
    assert 0 < result.home_win < 1
    assert 0 < result.draw < 1
    assert 0 < result.away_win < 1
    assert result.home_win + result.draw + result.away_win == pytest.approx(1.0, abs=1e-12)
    assert 0 < result.over_2_5 < 1
    assert 0 < result.btts_yes < 1


def test_poisson_rejects_invalid_expectations():
    with pytest.raises(ValueError):
        poisson_baseline(0, 1.2)
