import pytest

from betano_analyzer.value_engine import fair_market, value_signal


def test_fair_market_removes_margin():
    fair = fair_market(("home", "draw", "away"), (1.90, 3.50, 4.20), "1x2")
    assert fair.overround > 0
    assert abs(sum(fair.fair_probabilities) - 1) < 1e-9
    assert fair.fair_odds[0] > 1.90


def test_value_signal_positive_ev():
    signal = value_signal(2.10, 0.50, "home")
    assert signal.ev == pytest.approx(0.05)
    assert signal.edge == pytest.approx(0.05)
    assert signal.rating == "interesante"


def test_invalid_market_rejected():
    with pytest.raises(ValueError):
        fair_market(("home", "away"), (1.0, 2.0))
