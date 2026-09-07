import pytest

from betano_analyzer.opportunities import score_opportunity


def test_score_opportunity_uses_fused_probability():
    result = score_opportunity(
        match_id=1,
        match="A vs B",
        market="1x2_ft",
        selection="home",
        odds=1.80,
        model_probability=0.60,
        consensus=3,
        confidence=0.80,
        market_probability=0.55,
        model_probabilities=[0.60, 0.62],
    )
    assert result.model_probability == pytest.approx(0.586)
    assert result.edge == pytest.approx(0.0304444, abs=1e-6)
    assert result.probability_source == "model+market_consensus"


def test_score_opportunity_rejects_invalid_odds():
    with pytest.raises(ValueError):
        score_opportunity(match_id=1, match="A vs B", market="1x2_ft", selection="home", odds=1.0, model_probability=0.60)
