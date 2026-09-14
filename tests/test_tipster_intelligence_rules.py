from betano_analyzer.tipster_intelligence import (
    StatisticalEvidence,
    TipsterPick,
    analyze_pick,
    safer_market,
    select_best_combinada,
)


def pick(event: str, odds: float, selection: str = "home") -> object:
    return TipsterPick("test", "tipster", event, "1x2", selection, odds=odds)


def evidence() -> StatisticalEvidence:
    return StatisticalEvidence(
        model_probability=0.72,
        market_probability=0.58,
        recent_form_score=0.72,
        referee_score=0.65,
        agreement_score=0.75,
        data_completeness=1.0,
        sample_size=30,
    )


def test_local_is_converted_to_double_chance():
    result = safer_market(pick("A vs B", 1.70))
    assert result.safer_market == "double chance"
    assert result.safer_selection == "1X"


def test_over_three_is_reduced_to_over_two():
    result = safer_market(TipsterPick("x", "tipster", "A vs B", "goals", "Over 3", odds=1.80))
    assert result.safer_selection == "Over 2"


def test_value_requires_edge_and_reasonable_evidence():
    result = analyze_pick(pick("A vs B", 1.70), evidence())
    assert result.status == "VALUE"
    assert result.edge is not None and result.edge > 0.04


def test_outside_odds_band_is_rejected():
    result = analyze_pick(pick("A vs B", 3.00), evidence())
    assert result.status == "REJECT_ODDS"


def test_best_combination_stays_at_two_or_three_legs_and_under_2_5():
    candidates = [
        analyze_pick(pick("A vs B", 1.55), evidence()),
        analyze_pick(pick("C vs D", 1.45), evidence()),
        analyze_pick(pick("E vs F", 1.40), evidence()),
    ]
    selected = select_best_combinada(candidates)
    assert len(selected) in {2, 3}
    total = 1.0
    for item in selected:
        total *= item.offered_odds or 1.0
    assert 1.40 <= total <= 2.50
