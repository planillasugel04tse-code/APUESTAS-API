from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ..arbitrage import _is_live, find_arbitrage
from ..db import connect
from ..final_selector import build_final_selection
from ..ingest import normalize_market
from ..master_radar import build_master_radar
from ..matching import choose_team_match
from ..radar_value import build_value_radar
from .parser import ParsedTelegramPick, parse_telegram_message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _team_key(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9à-ÿ]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _match_event(db, pick: ParsedTelegramPick):
    rows = db.execute("SELECT * FROM matches WHERE status IN ('scheduled','live','in_play') ORDER BY kickoff").fetchall()
    candidate = choose_team_match(pick.home_team, pick.away_team, [dict(row) for row in rows])
    if candidate is None:
        return None
    return next((row for row in rows if int(row["id"]) == candidate.match_id), None)


def _latest_betano_quote(db, match_id: int, market: str, selection: str, line: float | None):
    rows = db.execute(
        """SELECT * FROM odds
           WHERE match_id=? AND LOWER(bookmaker) LIKE 'betano%'
             AND LOWER(market)=LOWER(?) AND LOWER(selection)=LOWER(?)
             AND ((line IS NULL AND ? IS NULL) OR line=?)
           ORDER BY captured_at DESC, id DESC""",
        (match_id, market, selection, line, line),
    ).fetchall()
    return rows[0] if rows else None


def _candidate(items: list[dict], match_id: int, market: str, selection: str, line: float | None):
    for item in items:
        if item.get("match_id") == match_id and str(item.get("market", "")).lower() == market.lower() and str(item.get("selection", "")).lower() == selection.lower() and item.get("line") == line:
            return item
    return None


def _ensure_tipster_and_pick(db, parsed: ParsedTelegramPick, match_id: int, market: str, selection: str) -> int:
    tipster = db.execute("SELECT id FROM tipsters WHERE name=?", (parsed.tipster,)).fetchone()
    if tipster:
        tipster_id = int(tipster["id"])
    else:
        cur = db.execute("INSERT INTO tipsters(name,source,active) VALUES(?,?,1)", (parsed.tipster, "Telegram"))
        tipster_id = int(cur.lastrowid)
    existing = db.execute(
        """SELECT id FROM picks WHERE match_id=? AND tipster_id=?
           AND LOWER(original_market)=LOWER(?) AND LOWER(original_selection)=LOWER(?)
           AND ABS(COALESCE(original_odds,0)-?) < 0.0001
           ORDER BY id DESC LIMIT 1""",
        (match_id, tipster_id, market, selection, parsed.odds),
    ).fetchone()
    if existing:
        return int(existing["id"])
    cur = db.execute(
        """INSERT INTO picks(match_id,tipster_id,original_market,original_selection,original_odds,
                              conservative_market,conservative_selection,conservative_odds,
                              confidence,probability,probability_source,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (match_id, tipster_id, market, selection, parsed.odds, None, None, None,
         parsed.confidence, None, "telegram_source", _now()),
    )
    return int(cur.lastrowid)


def process_telegram_signal(raw_text: str, *, channel: str, message_id: str, tipster: str | None = None) -> dict:
    """Telegram input adapter. Decisions are delegated to existing core engines."""
    parsed = parse_telegram_message(raw_text, channel=channel, tipster=tipster)
    created_at = _now()
    signal_id = f"tg-{uuid.uuid4().hex[:12]}"

    with connect() as db:
        existing = db.execute("SELECT signal_id FROM telegram_signals WHERE channel=? AND message_id=?", (channel, message_id)).fetchone()
        if existing:
            return {"status": "already_processed", "signal_id": existing["signal_id"], "channel": channel, "message_id": message_id}

        parsed_json = json.dumps(parsed.__dict__, ensure_ascii=False)
        if not parsed.is_valid:
            db.execute("INSERT INTO telegram_messages(channel,message_id,raw_text,status,parsed_data,received_at) VALUES(?,?,?,?,?,?)", (channel, message_id, raw_text, "failed", parsed_json, created_at))
            db.execute("INSERT INTO telegram_signals(signal_id,channel,message_id,tipster,raw_text,home_team,away_team,competition,market,selection,tipster_odds,matched_event_id,match_status,confidence,stake,analysis_result,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (signal_id, channel, message_id, parsed.tipster, raw_text, parsed.home_team, parsed.away_team, parsed.competition, parsed.market, parsed.selection, parsed.odds, None, "invalid", parsed.confidence, parsed.stake, json.dumps({"error": parsed.error_reason}, ensure_ascii=False), created_at))
            db.commit()
            return {"status": "failed", "signal_id": signal_id, "error": parsed.error_reason}

        event = _match_event(db, parsed)
        if event is None:
            analysis = {"status": "pending_match", "tipster_odds": parsed.odds, "betano_current_odds": None}
            db.execute("INSERT INTO telegram_messages(channel,message_id,raw_text,status,parsed_data,received_at) VALUES(?,?,?,?,?,?,?)", (channel, message_id, raw_text, "pending_match", parsed_json, created_at))
            db.execute("INSERT INTO telegram_signals(signal_id,channel,message_id,tipster,raw_text,home_team,away_team,competition,market,selection,tipster_odds,matched_event_id,match_status,confidence,stake,analysis_result,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (signal_id, channel, message_id, parsed.tipster, raw_text, parsed.home_team, parsed.away_team, parsed.competition, parsed.market, parsed.selection, parsed.odds, None, "pending_match", parsed.confidence, parsed.stake, json.dumps(analysis), created_at))
            db.commit()
            return {"status": "pending_match", "signal_id": signal_id, "analysis": analysis}

        canonical_market, canonical_selection = normalize_market(parsed.market, parsed.selection)
        pick_id = _ensure_tipster_and_pick(db, parsed, int(event["id"]), canonical_market, canonical_selection)
        quote = _latest_betano_quote(db, int(event["id"]), canonical_market, canonical_selection, parsed.line)
        betano_current_odds = float(quote["odds"]) if quote else None
        betano_odds_captured_at = str(quote["captured_at"]) if quote else None
        analysis = {
            "status": "matched",
            "tipster_odds": parsed.odds,
            "betano_current_odds": betano_current_odds,
            "betano_odds_captured_at": betano_odds_captured_at,
            "market": canonical_market,
            "selection": canonical_selection,
            "line": parsed.line,
            "pick_id": pick_id,
            "source_price_delta": round((betano_current_odds - parsed.odds), 4) if betano_current_odds is not None else None,
            "source_price_note": "tipster_odds is the published Telegram price; betano_current_odds is the latest Betano snapshot",
        }

        value = build_value_radar(limit=100, offered_bookmaker="Betano")
        value_item = _candidate(value.get("opportunities", []), int(event["id"]), canonical_market, canonical_selection, parsed.line)
        master = build_master_radar(limit=100)
        master_item = _candidate(master.get("opportunities", []), int(event["id"]), canonical_market, canonical_selection, parsed.line)
        final = build_final_selection(limit=100)
        final_item = _candidate(final.get("opportunities", []), int(event["id"]), canonical_market, canonical_selection, parsed.line)
        analysis.update({"value_engine": value_item, "master_radar_engine": master_item, "final_selector_engine": final_item})

        live = _is_live(event["kickoff"], status=event["status"])
        arbitrages = find_arbitrage(limit=20, live=live, match_id=int(event["id"]))
        analysis["surebets"] = [a.__dict__ for a in arbitrages if a.market.lower() == canonical_market.lower() and a.line == parsed.line]

        db.execute("INSERT INTO telegram_messages(channel,message_id,raw_text,status,pick_id,parsed_data,received_at) VALUES(?,?,?,?,?,?,?)", (channel, message_id, raw_text, "processed", pick_id, parsed_json, created_at))
        db.execute("""INSERT INTO telegram_signals(
            signal_id,channel,message_id,tipster,raw_text,home_team,away_team,competition,
            market,selection,tipster_odds,matched_event_id,match_status,confidence,stake,
            analysis_result,created_at,betano_current_odds,betano_odds_captured_at,line
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            signal_id, channel, message_id, parsed.tipster, raw_text, parsed.home_team,
            parsed.away_team, parsed.competition, canonical_market, canonical_selection,
            parsed.odds, event["id"], "matched", parsed.confidence, parsed.stake,
            json.dumps(analysis, ensure_ascii=False), created_at, betano_current_odds,
            betano_odds_captured_at, parsed.line,
        ))
        db.commit()

    return {"status": "success", "signal_id": signal_id, "match_id": event["id"], "pick_id": pick_id, "analysis": analysis}
