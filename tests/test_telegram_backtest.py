import uuid
import pytest
from src.database import db
from src.telegram.pipeline import process_telegram_message
from src.statistics.trends import PerformanceTrends

def test_telegram_signal_backtest_engine_integration():
    # 1. Seed event
    event = {
        "event_id": "evt-bt-arsenal-chelsea",
        "sport": "Soccer",
        "league": "Premier League",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "market": "1X2",
        "timestamp": "2026-09-10T16:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {"home_win": 1.90, "draw": 3.40, "away_win": 3.80}
            }
        ]
    }
    db.save_events([event])

    # 2. Process Telegram tipster signal
    raw_msg = "Arsenal vs Chelsea\nGana Local @ 1.85\nStake 2/10"
    channel = "@EPLBacktestChannel"
    msg_id = f"bt-msg-{uuid.uuid4().hex[:8]}"

    res = process_telegram_message(raw_text=raw_msg, channel=channel, message_id=msg_id)
    assert res["status"] == "success"
    assert res["match_status"] == "matched"
    assert res["betano_current_odds"] == 1.90

    # 3. Create historical match outcome (Arsenal 3 - 1 Chelsea)
    historical_matches = [
        {
            "event_id": "evt-bt-arsenal-chelsea",
            "sport": "Soccer",
            "league": "Premier League",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_goals": 3,
            "away_goals": 1,
            "date": "2026-09-10"
        }
    ]

    signals = db.get_telegram_signals()
    target_sig = [s for s in signals if s["message_id"] == msg_id]

    # 4. Run Backtesting Engine PerformanceTrends.evaluate_signals_backtest
    bt_report = PerformanceTrends.evaluate_signals_backtest(target_sig, historical_matches)

    assert bt_report["total_signals"] == 1
    assert bt_report["settled_signals"] == 1
    assert bt_report["wins"] == 1
    assert bt_report["losses"] == 0
    assert bt_report["hit_rate_percentage"] == 100.0
    assert bt_report["profit"] == 1.80  # stake=2, odds=1.90 -> payout=3.80, profit=1.80
    assert bt_report["roi_percentage"] == 90.0

def test_api_telegram_backtest_endpoint():
    from app import app
    client = app.test_client()

    res = client.get("/api/telegram/backtest")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert "report" in json_data
    assert "total_signals" in json_data["report"]
