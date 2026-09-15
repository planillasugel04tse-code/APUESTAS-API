from betano_analyzer.arbitrage import (
    classify_bookmaker,
    _is_peru_bookmaker,
    _valid_world_bookmaker_mix,
    _world_bookmaker_mix,
)


def test_peru_plus_international_is_valid():
    selected = {
        "home": ("Betano", 2.20),
        "away": ("Pinnacle", 2.20),
    }
    assert _valid_world_bookmaker_mix(selected)
    assert _world_bookmaker_mix(selected) == "PERU + INTERNATIONAL"


def test_international_plus_international_is_valid():
    selected = {
        "home": ("Pinnacle", 2.20),
        "away": ("Betfair", 2.20),
    }
    assert _valid_world_bookmaker_mix(selected)
    assert _world_bookmaker_mix(selected) == "INTERNATIONAL + INTERNATIONAL"


def test_peru_plus_peru_is_rejected_from_world():
    selected = {
        "home": ("Betano", 2.20),
        "away": ("Apuesta Total", 2.20),
    }
    assert not _valid_world_bookmaker_mix(selected)
    assert _world_bookmaker_mix(selected) == "PERU + PERU"


def test_pinnacle_is_not_classified_as_peru():
    assert not _is_peru_bookmaker("Pinnacle")
    assert not _is_peru_bookmaker("pinnacle")


def test_bet365_is_verified_as_peru():
    assert classify_bookmaker("Bet365") == "PERU"
    assert classify_bookmaker("bet365.pe") == "PERU"
    assert _is_peru_bookmaker("bet365")


def test_regional_betano_slug_is_classified_as_peru():
    assert _is_peru_bookmaker("betano.pe")
