from betano_analyzer.arbitrage import _integer_stake_plan


def test_integer_stake_plan_hits_requested_profit_targets():
    outcomes = {
        "home": {"odds": 2.10},
        "draw": {"odds": 3.80},
        "away": {"odds": 4.20},
    }

    for target in (250, 500, 1000, 3000, 5000):
        plan = _integer_stake_plan(outcomes, target)
        assert plan["guaranteed_profit"] >= target
        assert plan["total_stake"] == sum(plan["stakes"].values())
        assert all(stake >= 1 for stake in plan["stakes"].values())


def test_integer_stake_plan_rejects_non_surebet():
    outcomes = {
        "home": {"odds": 1.80},
        "away": {"odds": 1.80},
    }

    try:
        _integer_stake_plan(outcomes, 250)
    except ValueError as exc:
        assert "not a surebet" in str(exc)
    else:
        raise AssertionError("non-surebet must be rejected")
