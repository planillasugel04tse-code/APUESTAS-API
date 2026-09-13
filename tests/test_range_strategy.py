import pytest

from betano_analyzer.range_strategy import analyze_range, probability_between_lines


def test_probability_between_lines_is_zero_without_integer_gap():
    assert probability_between_lines(2.5, 3.5, 2.5) == 0.0


def test_analyze_range_detects_goal_line_gap():
    gaps = analyze_range("goals", [1.5, 2.5, 4.0], 2.2)
    assert len(gaps) == 2
    assert gaps[0].lower_line == 1.5
    assert gaps[0].upper_line == 2.5
    assert gaps[0].gap == 1.0
    assert 0 <= gaps[0].probability_between <= 1
    assert gaps[0].interpretation in {"BAJO", "MEDIO", "ALTO"}


def test_analyze_range_supports_corners_and_rejects_other_markets():
    assert analyze_range("corners", [8.5, 10.5], 9.2)
    with pytest.raises(ValueError):
        analyze_range("cards", [3.5, 4.5], 4.0)
