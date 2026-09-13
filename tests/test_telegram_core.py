from datetime import datetime, timezone, timedelta


def test_arbitrage_uses_match_status_for_live_classification(monkeypatch):
    from betano_analyzer import arbitrage

    now = datetime.now(timezone.utc)
    fresh_ts = (now - timedelta(minutes=1)).isoformat()

    class Row(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)

    rows = [
        Row(match_id=1, bookmaker="Betano", market="1x2_ft", selection="home", line=None, odds=2.1,
            captured_at=fresh_ts, home_team="A", away_team="B", competition="Test League",
            kickoff="2026-09-10T20:00:00+00:00", status="live"),
        Row(match_id=1, bookmaker="Book2", market="1x2_ft", selection="draw", line=None, odds=4.5,
            captured_at=fresh_ts, home_team="A", away_team="B", competition="Test League",
            kickoff="2026-09-10T20:00:00+00:00", status="live"),
        Row(match_id=1, bookmaker="Book3", market="1x2_ft", selection="away", line=None, odds=4.5,
            captured_at=fresh_ts, home_team="A", away_team="B", competition="Test League",
            kickoff="2026-09-10T20:00:00+00:00", status="live"),
    ]

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeDB:
        def execute(self, *args):
            return FakeCursor(rows)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(arbitrage, "connect", lambda: FakeDB())
    live_result = arbitrage.find_arbitrage(live=True, match_id=1)
    pre_result = arbitrage.find_arbitrage(live=False, match_id=1)
    assert live_result and live_result[0].mode == "live"
    assert pre_result == []
