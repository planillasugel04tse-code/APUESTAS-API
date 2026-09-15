from betano_analyzer.arbitrage import build_target_profit_plans, calculate_stakes


def test_fixed_stake_uses_whole_units():
    result = calculate_stakes({"home": {"odds": 2.2}, "draw": {"odds": 3.6}, "away": {"odds": 4.2}}, 100)
    assert isinstance(result["total_stake"], int)
    assert all(isinstance(value, int) for value in result["stakes"].values())
    assert isinstance(result["guaranteed_profit"], int)


def test_standard_profit_targets_are_integer_plans():
    plans = build_target_profit_plans({"home": {"odds": 2.2}, "draw": {"odds": 3.6}, "away": {"odds": 4.2}})
    assert set(plans) == {250, 500, 1000, 3000, 5000}
    for target, plan in plans.items():
        assert isinstance(plan["total_stake"], int)
        assert isinstance(plan["guaranteed_profit"], int)
        assert plan["guaranteed_profit"] >= target
        assert all(isinstance(value, int) for value in plan["stakes"].values())
