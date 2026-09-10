import uuid
import pytest
from src.database import db
from src.telegram.pipeline import process_telegram_message

def test_telegram_value_bet_master_radar_approved():
    # 1. Event where Betano PE odds are 2.15 vs Tipster odds of 1.90 (Value Bet!)
    event = {
        "event_id": "evt-de-mancity-arsenal-101",
        "sport": "Soccer",
        "league": "Premier League",
        "home_team": "Manchester City",
        "away_team": "Arsenal",
        "market": "1X2",
        "timestamp": "2026-09-10T21:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {"home_win": 2.15, "draw": 3.40, "away_win": 3.60}
            }
        ]
    }
    db.save_events([event])

    raw_msg = "Manchester City vs Arsenal\nGana Local @ 1.90\nStake 4/10"
    channel = "@EPLMasterTips"
    msg_id = f"de-msg-{uuid.uuid4().hex[:8]}"

    res = process_telegram_message(raw_text=raw_msg, channel=channel, message_id=msg_id)

    assert res["status"] == "success"
    assert res["match_status"] == "matched"
    assert res["tipster_odds"] == 1.90
    assert res["betano_current_odds"] == 2.15
    assert res["radar_classification"] == "ELITE_VALUE"
    assert res["final_selector_status"] == "APPROVED"
    assert res["analysis"]["clv_movement"] == "UPWARDS_VALUE_INCREASED"

    # Check that opportunity is in db.get_opportunities()
    opps = db.get_opportunities()
    matched_opp = next((o for o in opps if f"opp-tg-{res['signal_id']}" == o["opportunity_id"]), None)
    assert matched_opp is not None
    assert matched_opp["details"]["tipster_odds"] == 1.90
    assert matched_opp["details"]["betano_current_odds"] == 2.15

def test_telegram_odds_dropped_expired_value():
    # 2. Event where Betano odds dropped to 1.50 vs Tipster odds of 1.90 (No longer holds value!)
    event = {
        "event_id": "evt-de-psg-lyon-102",
        "sport": "Soccer",
        "league": "Ligue 1",
        "home_team": "PSG",
        "away_team": "Lyon",
        "market": "1X2",
        "timestamp": "2026-09-10T21:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {"home_win": 1.50, "draw": 4.00, "away_win": 6.00}
            }
        ]
    }
    db.save_events([event])

    raw_msg = "PSG vs Lyon\nGana Local @ 1.90\nStake 3/10"
    channel = "@Ligue1Tips"
    msg_id = f"de-msg-expired-{uuid.uuid4().hex[:8]}"

    res = process_telegram_message(raw_text=raw_msg, channel=channel, message_id=msg_id)

    assert res["status"] == "success"
    assert res["match_status"] == "matched"
    assert res["tipster_odds"] == 1.90
    assert res["betano_current_odds"] == 1.50
    assert res["radar_classification"] == "NO_VALUE_EXPIRED"
    assert res["final_selector_status"] == "EXPIRED_VALUE"
    assert res["analysis"]["clv_movement"] == "DOWNWARDS_ODDS_DROPPED"

    # Crucial Rule 6 & 7: Signal IS PRESERVED in telegram_signals for tipster historical performance!
    signals = db.get_telegram_signals()
    sig_record = next(s for s in signals if s["signal_id"] == res["signal_id"])
    assert sig_record["tipster_odds"] == 1.90
    assert sig_record["betano_current_odds"] == 1.50
    assert sig_record["analysis_result"]["final_selector_status"] == "EXPIRED_VALUE"

def test_telegram_surebet_arbitrage():
    # 3. Event with multi-bookmaker arbitrage opportunity
    event = {
        "event_id": "evt-de-barca-atletico-103",
        "sport": "Soccer",
        "league": "La Liga",
        "home_team": "Barcelona",
        "away_team": "Atletico Madrid",
        "market": "1X2",
        "timestamp": "2026-09-10T21:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {"home_win": 2.20, "draw": 3.60, "away_win": 3.80}
            },
            {
                "name": "Pinnacle",
                "country": "Global",
                "odds": {"home_win": 1.90, "draw": 4.10, "away_win": 4.50}
            }
        ]
    }
    db.save_events([event])

    raw_msg = "Barcelona vs Atletico Madrid\nGana Local @ 2.00\nStake 5/10"
    channel = "@LaLigaVIP"
    msg_id = f"de-msg-sb-{uuid.uuid4().hex[:8]}"

    res = process_telegram_message(raw_text=raw_msg, channel=channel, message_id=msg_id)

    assert res["status"] == "success"
    assert res["match_status"] == "matched"
    assert res["final_selector_status"] == "APPROVED"
    assert res["radar_classification"] in ("ELITE_VALUE", "SUREBET_ARBITRAGE")

def test_telegram_unmatched_pending():
    # 4. Signal for team not in database
    raw_msg = "Celtic vs Rangers\nGana Local @ 1.80"
    channel = "@ScotlandTips"
    msg_id = f"de-msg-pending-{uuid.uuid4().hex[:8]}"

    res = process_telegram_message(raw_text=raw_msg, channel=channel, message_id=msg_id)

    assert res["status"] == "success"
    assert res["match_status"] == "pending_match"
    assert res["final_selector_status"] == "PENDING_MATCH"
    assert res["betano_current_odds"] is None
