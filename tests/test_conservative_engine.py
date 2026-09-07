from betano_analyzer.conservative_engine import transform


def test_home_win_becomes_double_chance():
    result = transform("1x2", "Home")
    assert result.conservative_market == "double_chance"
    assert result.conservative_selection == "1X"


def test_away_win_becomes_double_chance():
    result = transform("1x2", "Away")
    assert result.conservative_selection == "X2"


def test_over_goals_is_reduced():
    result = transform("goals", "Over 2.5")
    assert result.conservative_selection == "Over 2"


def test_under_goals_is_raised():
    result = transform("goals", "Under 2.5")
    assert result.conservative_selection == "Under 3"


def test_corners_are_reduced_without_excessive_jump():
    result = transform("corners", "Over 9.5")
    assert result.conservative_selection == "Over 7.5"


def test_cards_are_reduced():
    result = transform("cards", "Over 4.5")
    assert result.conservative_selection == "Over 3.5"


def test_unsupported_market_is_not_invented():
    result = transform("btts", "Yes")
    assert result.conservative_selection == "Yes"
    assert result.conservative_market == "btts"
