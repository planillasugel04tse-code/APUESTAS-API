import pytest

from betano_analyzer.stake import allocate_stakes


def test_allocate_stakes_equal_return():
    result = allocate_stakes({"home": 2.2, "away": 2.2}, 100)
    assert result.guaranteed_return == pytest.approx(110.0)
    assert result.guaranteed_profit == pytest.approx(10.0)
    assert sum(result.stakes.values()) == pytest.approx(100.0)
    assert result.stakes["home"] == pytest.approx(50.0)


def test_allocate_stakes_rejects_non_arbitrage():
    with pytest.raises(ValueError, match="no forman una surebet"):
        allocate_stakes({"home": 1.8, "away": 1.8}, 100)


def test_allocate_stakes_rejects_invalid_total():
    with pytest.raises(ValueError, match="mayor que 0"):
        allocate_stakes({"home": 2.2, "away": 2.2}, 0)
