import pytest

from betano_analyzer.model_selection import evaluate_model_probability


def test_model_value_requires_conservative_edge():
    result = evaluate_model_probability(0.60, 1.80)
    assert result.usable is True
    assert result.fair_odds == pytest.approx(1.66666667)
    assert result.edge == pytest.approx(0.08)
    assert result.expected_value == pytest.approx(0.08)


def test_model_does_not_force_a_bet():
    result = evaluate_model_probability(0.52, 1.80)
    assert result.usable is False
    assert result.reason == "insufficient_model_edge"


def test_model_selection_validates_inputs():
    with pytest.raises(ValueError):
        evaluate_model_probability(0.0, 2.0)
    with pytest.raises(ValueError):
        evaluate_model_probability(0.60, 1.0)
