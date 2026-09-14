from betano_analyzer.tipster_intelligence import (
    StatisticalEvidence,
    TipsterPick,
    analyze_pick,
    safer_market,
    select_best_combinada,
)


def test_home_pick_gets_double_chance():
    pick = TipsterPick(source="x", source_type="tipster", event="A vs B", market="1x2", selection="home", odds=1.70)
    safer = safer_market(pick)
    assert safer.safer_selection == "1X"


def test_over_line_is_reduced():
    pick = TipsterPick(source="x", source_type="tipster", event="A vs B", market="goals", selection="Over 3", odds=1.80)
    safer = safer_market(pick)
    assert safer.safer_selection == "Over 2"


def test_value_requires_odds_in_hard_range():
    pick = TipsterPick(source="x", source_type="tipster", event="A vs B", market="goals", selection="Over 2.5", odds=1.80)
    result = analyze_pick(pick, StatisticalEvidence(model_probability=0.62, agreement_score=0.7, data_completeness=1))
    assert result.status == "VALUE"
    assert result.edge is not None and result.edge > 0


def test_combinada_has_at_most_three_distinct_events():
    candidates = []
    for i in range(5):
        pick = TipsterPick(source="x", source_type="tipster", event=f"A{i} vs B{i}", market="1x2", selection="home", odds=1.45)
        candidates.append(analyze_pick(pick, StatisticalEvidence(model_probability=0.75, agreement_score=0.8, data_completeness=1)))
    selected = select_best_combinada(candidates)
    assert 1 <= len(selected) <= 3
