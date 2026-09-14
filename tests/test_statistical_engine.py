from betano_analyzer.statistical_engine import TeamMatch, build_report, probability_for_selection


def test_empty_history_is_insufficient():
    report = build_report([])
    assert report.status == "DATOS_INSUFICIENTES"
    assert report.data_completeness == 0.0


def test_short_history_is_not_presented_as_complete():
    report = build_report([TeamMatch(2, 0), TeamMatch(1, 1)])
    assert report.sample_size == 2
    assert report.status == "DATOS_INSUFICIENTES"
    assert report.data_completeness == 0.4


def test_complete_history_produces_model_probabilities():
    history = [
        TeamMatch(2, 0), TeamMatch(1, 1), TeamMatch(3, 1),
        TeamMatch(0, 1), TeamMatch(2, 2), TeamMatch(3, 0),
    ]
    report = build_report(history)
    assert report.status == "OK"
    assert 0 <= report.over_25_probability <= 1
    assert 0 <= report.btts_probability <= 1
    assert probability_for_selection(report, "goals", "Over 2.5") == report.over_25_probability
    assert probability_for_selection(report, "1x2", "local") == report.win_rate
