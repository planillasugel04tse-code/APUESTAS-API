import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from src.database import db
from src.odds.matcher import EventMatcher
from src.calculators.roi import ROICalculator
from src.calculators.stakes import StakeCalculator
from src.calculators.probability import ProbabilityCalculator
from src.analyzers.surebet import SurebetAnalyzer
from .parser import parse_telegram_message

logger = logging.getLogger("betting_analyzer.telegram.pipeline")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def process_telegram_message(
    raw_text: str,
    channel: str = "@TeleBetChannel",
    message_id: Optional[str] = None,
    tipster_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Complete end-to-end Decision Engine integration:
    TELEGRAM -> PARSER -> MATCHING -> BETANO ODDS -> VALUE / EDGE / EV -> SUREBET CHECK -> MASTER RADAR -> FINAL SELECTOR -> HISTORICAL & DASHBOARD PERSISTENCE
    """
    timestamp = _now_iso()
    msg_id = message_id or f"msg-{int(datetime.now(timezone.utc).timestamp()*1000)}"

    # 1. Deduplication check in SQLite
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM telegram_messages WHERE channel=? AND message_id=?",
            (channel, msg_id)
        )
        existing = cursor.fetchone()

        if existing and dict(existing).get("status") in ("pick_created", "already_processed"):
            return {
                "status": "already_processed",
                "message_id": msg_id,
                "channel": channel,
                "signal_id": dict(existing).get("pick_id"),
            }

    # 2. Parse Telegram Message
    parsed = parse_telegram_message(raw_text, channel=channel, tipster=tipster_name)
    parsed_json = json.dumps({
        "home_team": parsed.home_team,
        "away_team": parsed.away_team,
        "competition": parsed.competition,
        "market": parsed.market,
        "selection": parsed.selection,
        "odds": parsed.odds,
        "stake": parsed.stake,
        "confidence": parsed.confidence,
        "is_valid": parsed.is_valid,
        "error_reason": parsed.error_reason,
    })

    if not parsed.is_valid:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO telegram_messages (channel, message_id, raw_text, status, parsed_data, received_at) VALUES (?, ?, ?, 'failed', ?, ?)",
                (channel, msg_id, raw_text, parsed_json, timestamp)
            )
            conn.commit()
        return {
            "status": "failed",
            "message_id": msg_id,
            "channel": channel,
            "error_reason": parsed.error_reason,
        }

    # 3. Match Telegram Signal with stored events from Betano / OddsPapi
    events = db.get_events()
    matched_event = None

    for ev in events:
        home_match = EventMatcher.match_team_names(parsed.home_team, ev.get("home_team", ""))
        away_match = EventMatcher.match_team_names(parsed.away_team, ev.get("away_team", ""))
        if home_match and away_match:
            matched_event = ev
            break

    signal_id = f"sig-{uuid.uuid4().hex[:12]}"
    match_status = "pending_match"
    matched_event_id = None
    betano_current_odds = None

    # Analysis data structures
    fair_prob = round(1.0 / parsed.odds, 4) if parsed.odds > 1.0 else 0.5
    fair_odds = ProbabilityCalculator.calculate_fair_odds(fair_prob)
    
    clv_movement = "NEUTRAL"
    radar_classification = "PENDING_MATCH"
    final_selector_status = "PENDING_MATCH"
    surebet_info: Optional[Dict[str, Any]] = None

    analysis_result: Dict[str, Any] = {
        "tipster_odds": parsed.odds,
        "betano_current_odds": None,
        "fair_probability": fair_prob,
        "fair_odds": fair_odds,
        "edge_percentage": 0.0,
        "ev": 0.0,
        "recommended_stake": parsed.stake,
        "recommended_kelly_stake": 0.0,
        "value_found": False,
        "clv_movement": "N/A",
        "radar_classification": "PENDING_MATCH",
        "final_selector_status": "PENDING_MATCH",
        "surebet": None,
    }

    if matched_event:
        matched_event_id = matched_event["event_id"]
        match_status = "matched"

        # Search for Betano PE / Betano odds specifically or best available
        bookmakers = matched_event.get("bookmakers", [])
        betano_bm = next((bm for bm in bookmakers if "betano" in bm["name"].lower()), None)
        
        if betano_bm:
            odds_dict = betano_bm.get("odds", {})
            selection_key = parsed.selection.lower()
            if parsed.selection == "1": selection_key = "home_win"
            elif parsed.selection == "X": selection_key = "draw"
            elif parsed.selection == "2": selection_key = "away_win"
            betano_current_odds = odds_dict.get(selection_key) or odds_dict.get(parsed.selection)
        
        # Fallback to best available odds across bookmakers if Betano PE specific outcome key differs
        if not betano_current_odds and bookmakers:
            extracted = EventMatcher.extract_best_odds(bookmakers)
            selection_key = parsed.selection.lower()
            if parsed.selection == "1": selection_key = "home_win"
            elif parsed.selection == "X": selection_key = "draw"
            elif parsed.selection == "2": selection_key = "away_win"
            if selection_key in extracted:
                betano_current_odds = extracted[selection_key]["odds"]

        # Check for Surebet arbitrage across bookmakers if event has multiple bookmakers
        if len(bookmakers) >= 2:
            sb_list = SurebetAnalyzer.analyze_event(matched_event, default_bankroll=100.0)
            if sb_list:
                surebet_info = sb_list[0]

    # 4. Perform Complete Decision Engine Calculation if current bookmaker odds exist
    if betano_current_odds:
        val_analysis = ROICalculator.calculate_value_edge(fair_prob, betano_current_odds)
        edge = val_analysis["edge_percentage"]
        ev = round((fair_prob * betano_current_odds - 1.0), 4)
        kelly_analysis = StakeCalculator.calculate_kelly_stake(
            bankroll=100.0,
            model_probability=fair_prob,
            odds=betano_current_odds,
            fraction=0.25
        )

        # Evaluate CLV / Odds Movement (Tipster odds vs Betano current odds)
        if betano_current_odds > parsed.odds:
            clv_movement = "UPWARDS_VALUE_INCREASED"
        elif betano_current_odds < parsed.odds:
            clv_movement = "DOWNWARDS_ODDS_DROPPED"
        else:
            clv_movement = "STABLE"

        # Master Radar Classification
        if edge >= 8.0:
            radar_classification = "ELITE_VALUE"
            final_selector_status = "APPROVED"
        elif edge >= 5.0:
            radar_classification = "STRONG_VALUE"
            final_selector_status = "APPROVED"
        elif edge >= 1.0:
            radar_classification = "MODERATE_VALUE"
            final_selector_status = "APPROVED"
        else:
            radar_classification = "NO_VALUE_EXPIRED"
            final_selector_status = "EXPIRED_VALUE"

        # If a Surebet was found, override selector to APPROVED
        if surebet_info:
            final_selector_status = "APPROVED"
            radar_classification = "SUREBET_ARBITRAGE"

        analysis_result.update({
            "betano_current_odds": betano_current_odds,
            "fair_probability": fair_prob,
            "fair_odds": fair_odds,
            "edge_percentage": edge,
            "ev": ev,
            "recommended_stake": parsed.stake,
            "recommended_kelly_stake": kelly_analysis["recommended_stake"],
            "value_found": edge > 0 or surebet_info is not None,
            "clv_movement": clv_movement,
            "radar_classification": radar_classification,
            "final_selector_status": final_selector_status,
            "surebet": surebet_info,
            "summary": f"Tipster @ {parsed.odds} vs Betano @ {betano_current_odds} -> Edge: {edge}% | Status: {final_selector_status}"
        })

    # 5. Persist signal, Master Radar opportunity, and message traceability in SQLite
    signal_record = {
        "signal_id": signal_id,
        "channel": channel,
        "message_id": msg_id,
        "tipster": parsed.tipster,
        "raw_text": raw_text,
        "home_team": parsed.home_team,
        "away_team": parsed.away_team,
        "competition": parsed.competition,
        "market": parsed.market,
        "selection": parsed.selection,
        "tipster_odds": parsed.odds,               # PRESERVE ORIGINAL TIPSTER ODDS
        "betano_current_odds": betano_current_odds, # PRESERVE CURRENT BETANO ODDS
        "matched_event_id": matched_event_id,
        "match_status": match_status,
        "confidence": parsed.confidence,
        "stake": parsed.stake,
        "analysis_result": analysis_result,
    }

    db.save_telegram_signal(signal_record)

    # Save to Master Radar Opportunities Table if APPROVED or matched
    if betano_current_odds and final_selector_status in ("APPROVED", "EXPIRED_VALUE"):
        opp_entry = {
            "opportunity_id": f"opp-tg-{signal_id}",
            "type": "valuebet" if not surebet_info else "surebet",
            "event_id": matched_event_id or f"evt-tg-{signal_id}",
            "sport": "Soccer",
            "league": parsed.competition or "Telegram Tipster",
            "home_team": parsed.home_team,
            "away_team": parsed.away_team,
            "market": parsed.market,
            "roi": analysis_result["edge_percentage"],
            "probability": fair_prob,
            "details": {
                "source": "Telegram",
                "tipster": parsed.tipster,
                "channel": channel,
                "tipster_odds": parsed.odds,
                "betano_current_odds": betano_current_odds,
                "clv_movement": clv_movement,
                "radar_classification": radar_classification,
                "final_selector_status": final_selector_status,
                "recommended_kelly_stake": analysis_result["recommended_kelly_stake"],
                "surebet": surebet_info
            }
        }
        db.save_opportunities([opp_entry])

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO telegram_messages (channel, message_id, raw_text, status, pick_id, parsed_data, received_at) VALUES (?, ?, ?, 'pick_created', ?, ?, ?)",
            (channel, msg_id, raw_text, signal_id, parsed_json, timestamp)
        )
        conn.commit()

    return {
        "status": "success",
        "signal_id": signal_id,
        "message_id": msg_id,
        "channel": channel,
        "match_status": match_status,
        "matched_event_id": matched_event_id,
        "home_team": parsed.home_team,
        "away_team": parsed.away_team,
        "market": parsed.market,
        "selection": parsed.selection,
        "tipster_odds": parsed.odds,
        "betano_current_odds": betano_current_odds,
        "radar_classification": radar_classification,
        "final_selector_status": final_selector_status,
        "analysis": analysis_result,
    }
