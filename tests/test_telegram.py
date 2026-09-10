import uuid
import pytest
from src.database import db
from src.telegram.parser import parse_telegram_message
from src.telegram.pipeline import process_telegram_message

def test_parse_1x2_local_win():
    text = "Real Madrid vs Barcelona\nGana Local @ 1.85\nStake 3/10"
    parsed = parse_telegram_message(text, channel="@TipsterSpain")
    assert parsed.is_valid is True
    assert parsed.home_team == "Real Madrid"
    assert parsed.away_team == "Barcelona"
    assert parsed.market == "1x2"
    assert parsed.selection == "1"
    assert parsed.odds == 1.85
    assert parsed.stake == 3.0
    assert parsed.confidence == 0.30

def test_parse_real_emoji_message():
    text = "🏆UEFA Champions League ⚽️Manchester United vs Sabah Baku  💰1.62 💵 200€ ⏰14:00🇨🇴 📊Alta 🔞RECUERDA JUGAR RESPONSABLE."
    parsed = parse_telegram_message(text, channel="@TuComviFutbol")
    assert parsed.is_valid is True
    assert parsed.home_team == "Manchester United"
    assert parsed.away_team == "Sabah Baku"
    assert parsed.market == "1x2"
    assert parsed.selection == "1"
    assert parsed.odds == 1.62

def test_parse_goals_over():
    text = "Manchester City - Liverpool\nMercado: Over 2.5 goles\nCuota: 1.95\nUnidades: 2"
    parsed = parse_telegram_message(text, channel="@EPLPicks")
    assert parsed.is_valid is True
    assert parsed.home_team == "Manchester City"
    assert parsed.away_team == "Liverpool"
    assert parsed.market == "goals"
    assert parsed.selection == "Over 2.5"
    assert parsed.odds == 1.95

def test_parse_btts():
    text = "Arsenal vs Chelsea\nAmbos Anotan SI @ 1.75\nStake 4"
    parsed = parse_telegram_message(text)
    assert parsed.is_valid is True
    assert parsed.market == "btts"
    assert parsed.selection == "Yes"
    assert parsed.odds == 1.75

def test_parse_double_chance():
    text = "Universitario contra Sporting Cristal\nDoble Opcion 1X @ 1.55"
    parsed = parse_telegram_message(text)
    assert parsed.is_valid is True
    assert parsed.home_team == "Universitario"
    assert parsed.away_team == "Sporting Cristal"
    assert parsed.market == "double_chance"
    assert parsed.selection == "1X"
    assert parsed.odds == 1.55

def test_invalid_message_no_match():
    text = "Hola a todos, hoy tenemos grandes partidos en la Premier League. ¡Atentos!"
    parsed = parse_telegram_message(text)
    assert parsed.is_valid is False
    assert "No se pudieron identificar los equipos" in parsed.error_reason

def test_process_telegram_message_end_to_end():
    test_event = {
        "event_id": "evt-real-barca-1001",
        "sport": "Soccer",
        "league": "La Liga",
        "home_team": "Real Madrid",
        "away_team": "Barcelona",
        "market": "1X2",
        "timestamp": "2026-09-10T20:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {
                    "home_win": 2.05,
                    "draw": 3.60,
                    "away_win": 3.40
                }
            }
        ]
    }
    db.save_events([test_event])

    text = "Real Madrid vs Barcelona\nGana Local @ 1.85\nStake 3/10"
    channel = "@TeleBetVIP"
    msg_id = f"msg-e2e-{uuid.uuid4().hex[:8]}"

    result = process_telegram_message(raw_text=text, channel=channel, message_id=msg_id)

    assert result["status"] == "success"
    assert result["match_status"] == "matched"
    assert result["matched_event_id"] == "evt-real-barca-1001"
    
    assert result["tipster_odds"] == 1.85
    assert result["betano_current_odds"] == 2.05
    assert result["analysis"]["value_found"] is True
    assert result["analysis"]["edge_percentage"] > 0

    signals = db.get_telegram_signals()
    assert len(signals) >= 1
    latest_sig = next(s for s in signals if s["message_id"] == msg_id)
    assert latest_sig["channel"] == channel
    assert latest_sig["raw_text"] == text
    assert latest_sig["tipster_odds"] == 1.85
    assert latest_sig["betano_current_odds"] == 2.05
    assert latest_sig["match_status"] == "matched"

def test_process_telegram_real_channel_message_end_to_end():
    real_event = {
        "event_id": "evt-manu-sabah-9900",
        "sport": "Soccer",
        "league": "UEFA Champions League",
        "home_team": "Manchester United",
        "away_team": "Sabah Baku",
        "market": "1X2",
        "timestamp": "2026-09-10T14:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {
                    "home_win": 1.80,
                    "draw": 3.50,
                    "away_win": 4.50
                }
            }
        ]
    }
    db.save_events([real_event])

    raw_msg = "🏆UEFA Champions League ⚽️Manchester United vs Sabah Baku  💰1.62 💵 200€ ⏰14:00🇨🇴 📊Alta 🔞RECUERDA JUGAR RESPONSABLE."
    channel = "@TuComviFutbol"
    msg_id = f"real-msg-{uuid.uuid4().hex[:8]}"

    result = process_telegram_message(raw_text=raw_msg, channel=channel, message_id=msg_id)

    assert result["status"] == "success"
    assert result["match_status"] == "matched"
    assert "evt-manu-sabah" in result["matched_event_id"]
    assert result["tipster_odds"] == 1.62
    assert result["betano_current_odds"] == 1.80
    assert result["analysis"]["edge_percentage"] == 11.11

def test_process_telegram_message_duplicate_prevention():
    text = "Arsenal vs Chelsea\nOver 2.5 goles @ 1.90"
    channel = "@EPLPicks"
    msg_id = f"msg-dup-{uuid.uuid4().hex[:8]}"

    res1 = process_telegram_message(raw_text=text, channel=channel, message_id=msg_id)
    assert res1["status"] == "success"

    res2 = process_telegram_message(raw_text=text, channel=channel, message_id=msg_id)
    assert res2["status"] == "already_processed"
    assert res2["signal_id"] == res1["signal_id"]

def test_process_telegram_unmatched_event():
    text = "Bayern Munich vs Borussia Dortmund\nGana Local @ 1.70"
    channel = "@BundesligaTips"
    msg_id = f"msg-unmatched-{uuid.uuid4().hex[:8]}"

    result = process_telegram_message(raw_text=text, channel=channel, message_id=msg_id)
    assert result["status"] == "success"
    assert result["match_status"] == "pending_match"
    assert result["betano_current_odds"] is None


def test_telegram_collector_listener_integration():
    from src.telegram.collector import TelegramCollector
    
    collector = TelegramCollector()
    assert collector.message_handler is not None

    test_event = {
        "event_id": "evt-inter-milan-9099",
        "sport": "Soccer",
        "league": "Serie A",
        "home_team": "Inter Milan",
        "away_team": "Juventus",
        "market": "1X2",
        "timestamp": "2026-09-10T18:00:00Z",
        "bookmakers": [
            {
                "name": "Betano PE",
                "country": "Peru",
                "odds": {
                    "home_win": 1.95,
                    "draw": 3.40,
                    "away_win": 3.80
                }
            }
        ]
    }
    db.save_events([test_event])

    raw_text = "Inter Milan vs Juventus\nGana Local @ 1.75\nStake 3/10"
    channel_name = "@SerieATips"
    msg_id = f"live-evt-{uuid.uuid4().hex[:8]}"

    res1 = collector.message_handler(raw_text, channel_name, msg_id)
    assert res1["status"] == "success"
    assert res1["match_status"] == "matched"
    assert res1["tipster_odds"] == 1.75
    assert res1["betano_current_odds"] == 1.95

    res2 = collector.message_handler(raw_text, channel_name, msg_id)
    assert res2["status"] == "already_processed"
    assert res2["signal_id"] == res1["signal_id"]
