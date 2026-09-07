from betano_analyzer import arbitrage
from betano_analyzer.db import initialize


def test_two_way_surebet_uses_distinct_bookmakers_and_allocates_stakes(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    initialize(db_path)

    with arbitrage.connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            ("demo-1", "Demo", "Local", "Visitante", "2026-09-07T20:00:00Z", "live"),
        )
        rows = [
            (1, "Betano PE", "goals", "over", 2.20),
            (1, "Apuesta Total", "goals", "under", 2.10),
            (1, "Betano PE", "goals", "under", 1.80),
            (1, "Apuesta Total", "goals", "over", 1.70),
        ]
        for match_id, bookmaker, market, selection, odds in rows:
            db.execute(
                "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
                (match_id, bookmaker, market, selection, odds, "2026-09-07T19:00:00Z", 2.5),
            )
        db.commit()

    monkeypatch.setattr(arbitrage, "connect", lambda: __import__("sqlite3").connect(db_path))
    # Reapply row_factory expected by the production function.
    original_connect = arbitrage.connect

    def connect_with_rows():
        connection = original_connect()
        connection.row_factory = __import__("sqlite3").Row
        return connection

    monkeypatch.setattr(arbitrage, "connect", connect_with_rows)
    result = arbitrage.find_arbitrage(
        bookmakers=["Betano PE", "Apuesta Total"],
        total_stake=100,
    )

    assert len(result) == 1
    opportunity = result[0]
    assert opportunity.profit_margin > 0
    assert opportunity.guaranteed_profit > 0
    assert round(sum(item["stake"] for item in opportunity.outcomes.values()), 2) == 100.0
    assert {item["bookmaker"] for item in opportunity.outcomes.values()} == {
        "Betano PE",
        "Apuesta Total",
    }


def test_no_surebet_when_inverse_sum_is_one_or_more(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    initialize(db_path)

    with arbitrage.connect(db_path) as db:
        db.execute(
            "INSERT INTO matches(external_id,competition,home_team,away_team,kickoff,status) VALUES(?,?,?,?,?,?)",
            ("demo-2", "Demo", "Local", "Visitante", "2026-09-07T20:00:00Z", "live"),
        )
        rows = [
            (1, "Betano PE", "goals", "over", 2.0),
            (1, "Apuesta Total", "goals", "under", 2.0),
        ]
        for match_id, bookmaker, market, selection, odds in rows:
            db.execute(
                "INSERT INTO odds(match_id,bookmaker,market,selection,odds,captured_at,line) VALUES(?,?,?,?,?,?,?)",
                (match_id, bookmaker, market, selection, odds, "2026-09-07T19:00:00Z", 2.5),
            )
        db.commit()

    import sqlite3

    def connect_with_rows():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(arbitrage, "connect", connect_with_rows)
    assert arbitrage.find_arbitrage(bookmakers=["Betano PE", "Apuesta Total"]) == []
