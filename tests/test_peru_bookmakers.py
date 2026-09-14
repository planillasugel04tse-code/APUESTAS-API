from betano_analyzer.bookmakers import _rows
from betano_analyzer.peru_bookmakers import registry_slugs


def test_peru_registry_uses_exact_oddspapi_slugs():
    assert registry_slugs() == ["betano.pe", "apuestatotal", "inkabet"]


def test_oddspapi_v4_bookmakers_shape_is_normalized():
    payload = [
        {"bookmakerName": "Betano PE", "slug": "betano.pe", "liveOdds": True, "cloneOf": None},
        {"bookmakerName": "Apuesta Total", "slug": "apuestatotal", "liveOdds": True, "cloneOf": None},
    ]

    rows = _rows(payload)

    assert rows[0] == {
        "name": "Betano PE",
        "slug": "betano.pe",
        "live_odds": True,
        "clone_of": None,
    }
    assert rows[1]["slug"] == "apuestatotal"
