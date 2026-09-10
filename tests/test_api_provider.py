from src.providers.api_provider import APIProvider


def _outcome(label: str, price: float) -> dict:
    return {
        "players": {
            "0": {
                "active": True,
                "bookmakerOutcomeId": label,
                "price": price,
            }
        }
    }


def test_oddspapi_normalizes_1x2_market():
    """OddsPapi 1X2 labels are converted to the internal schema."""
    provider = APIProvider(api_key="test-key")
    raw = [
        {
            "fixtureId": "fixture-1",
            "sportName": "Soccer",
            "tournamentName": "Liga 1 Peru",
            "participant1Name": "Alianza Lima",
            "participant2Name": "Universitario",
            "startTime": "2026-09-10T20:00:00.000Z",
            "bookmakerOdds": {
                "apuestatotal": {
                    "bookmakerIsActive": True,
                    "markets": {
                        "101": {
                            "marketActive": True,
                            "bookmakerMarketId": "moneyline",
                            "outcomes": {
                                "101": _outcome("home", 2.4),
                                "102": _outcome("draw", 3.4),
                                "103": _outcome("away", 3.1),
                            },
                        }
                    },
                },
                "betano.pe": {
                    "bookmakerIsActive": True,
                    "markets": {
                        "101": {
                            "marketActive": True,
                            "bookmakerMarketId": "moneyline",
                            "outcomes": {
                                "101": _outcome("home", 2.3),
                                "102": _outcome("draw", 3.5),
                                "103": _outcome("away", 3.2),
                            },
                        }
                    },
                },
            },
        }
    ]

    events = provider._normalize_oddspapi_response(raw)

    assert len(events) == 1
    assert events[0]["event_id"] == "fixture-1_1x2"
    assert events[0]["market"] == "1X2"
    assert events[0]["home_team"] == "Alianza Lima"
    assert events[0]["bookmakers"][0]["odds"]["home_win"] == 2.4


def test_oddspapi_normalizes_totals_market():
    """OddsPapi total line labels become over_X/under_X selections."""
    provider = APIProvider(api_key="test-key")
    raw = {
        "data": [
            {
                "fixtureId": "fixture-2",
                "participant1Name": "Peru A",
                "participant2Name": "Peru B",
                "bookmakerOdds": {
                    "inkabet": {
                        "bookmakerIsActive": True,
                        "markets": {
                            "106": {
                                "marketActive": True,
                                "bookmakerMarketId": "totals",
                                "outcomes": {
                                    "106": _outcome("2.5/over", 2.05),
                                    "107": _outcome("2.5/under", 1.9),
                                },
                            }
                        },
                    },
                    "pinnacle": {
                        "bookmakerIsActive": True,
                        "markets": {
                            "106": {
                                "marketActive": True,
                                "bookmakerMarketId": "totals",
                                "outcomes": {
                                    "106": _outcome("2.5/over", 2.1),
                                    "107": _outcome("2.5/under", 1.85),
                                },
                            }
                        },
                    },
                },
            }
        ]
    }

    events = provider._normalize_oddspapi_response(raw)

    assert len(events) == 1
    assert events[0]["market"] == "Over/Under Goals"
    assert events[0]["bookmakers"][0]["odds"]["over_2.5"] == 2.05
    assert events[0]["bookmakers"][0]["odds"]["under_2.5"] == 1.9


def test_account_response_does_not_expose_api_key(monkeypatch):
    """The local API must not return the secret OddsPapi key."""
    provider = APIProvider(api_key="secret-key")

    def fake_request(endpoint, params):
        return {"api_key": "secret-key", "subscriptions": []}

    monkeypatch.setattr(provider, "_request", fake_request)

    account = provider.get_account()

    assert account["configured"] is True
    assert "api_key" not in account


def test_oddspapi_keeps_single_bookmaker_event_for_visibility():
    """Single-bookmaker events are visible in odds view even if analyzers skip them."""
    provider = APIProvider(api_key="test-key")
    raw = [
        {
            "fixtureId": "fixture-3",
            "participant1Name": "Sporting Cristal",
            "participant2Name": "Melgar",
            "bookmakerOdds": {
                "betano.pe": {
                    "bookmakerIsActive": True,
                    "markets": {
                        "101": {
                            "marketActive": True,
                            "bookmakerMarketId": "moneyline",
                            "outcomes": {
                                "101": _outcome("home", 2.0),
                                "102": _outcome("draw", 3.2),
                                "103": _outcome("away", 3.7),
                            },
                        }
                    },
                }
            },
        }
    ]

    events = provider._normalize_oddspapi_response(raw)

    assert len(events) == 1
    assert events[0]["bookmakers"][0]["name"] == "Betano PE"
    assert provider.get_provider_status()["normalized_events"] == 1


def test_get_events_uses_fixture_id_for_odds_fallback(monkeypatch):
    """When tournaments are not configured, /v4/odds is called with fixtureId."""
    provider = APIProvider(api_key="test-key")
    provider.use_tournaments = False
    provider.max_fixtures = 1
    calls = []

    def fake_fetch_limited_fixtures():
        return [{"fixtureId": "fixture-4"}]

    def fake_request(endpoint, params):
        calls.append((endpoint, params))
        assert endpoint == "odds"
        assert params["fixtureId"] == "fixture-4"
        return {
            "fixtureId": "fixture-4",
            "participant1Name": "Alianza Lima",
            "participant2Name": "Melgar",
            "bookmakerOdds": {
                "apuestatotal": {
                    "bookmakerIsActive": True,
                    "markets": {
                        "101": {
                            "marketActive": True,
                            "bookmakerMarketId": "moneyline",
                            "outcomes": {
                                "101": _outcome("home", 2.1),
                                "102": _outcome("draw", 3.3),
                                "103": _outcome("away", 3.6),
                            },
                        }
                    },
                }
            },
        }

    monkeypatch.setattr(provider, "_fetch_limited_fixtures", fake_fetch_limited_fixtures)
    monkeypatch.setattr(provider, "_request", fake_request)

    events = provider.get_events()

    assert len(events) == 1
    assert calls[0][0] == "odds"
    assert provider.get_provider_status()["endpoint"] == "fixtures+odds"
    assert provider.get_provider_status()["fixtures_requested_for_odds"] == 1
