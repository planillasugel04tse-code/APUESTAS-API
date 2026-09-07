from betano_analyzer.clv import calculate_clv


def test_positive_clv():
    signal = calculate_clv(2.10, 1.95)
    assert round(signal.clv, 6) == round(2.10 / 1.95 - 1, 6)
    assert signal.direction == "positive"


def test_negative_clv():
    signal = calculate_clv(1.80, 1.90)
    assert signal.direction == "negative"
