import pytest

from betano_analyzer.probability_fusion import fuse_probabilities


def test_fusion_combines_model_and_market():
    result = fuse_probabilities([0.60, 0.62], market_probability=0.55, offered_odds=1.80)
    assert result.probability == pytest.approx(0.586)
    assert result.model_probability == pytest.approx(0.61)
    assert result.market_probability == pytest.approx(0.55)
    assert result.usable is True
    assert "market_consensus" in result.sources


def test_fusion_does_not_force_bet_when_price_has_no_edge():
    result = fuse_probabilities([0.52, 0.53], market_probability=0.51, offered_odds=1.80)
    assert result.usable is False
    assert result.reason == "insufficient_fused_edge"


def test_fusion_works_without_market_reference():
    result = fuse_probabilities([0.60, 0.62], offered_odds=1.80)
    assert result.probability == pytest.approx(0.61)
    assert result.market_probability is None
    assert result.usable is True


def test_fusion_validates_inputs():
    with pytest.raises(ValueError):
        fuse_probabilities([])
    with pytest.raises(ValueError):
        fuse_probabilities([1.0])
    with pytest.raises(ValueError):
        fuse_probabilities([0.6], offered_odds=1.0)
