from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .db import connect
from .opportunities import score_opportunity


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _tipster_weights(db, market: str) -> dict[int, float]:
    rows = db.execute("""SELECT t.id AS tipster_id, COUNT(*) AS picks,
                              SUM(pr.result='won') AS wins,
                              SUM(CASE WHEN pr.result='won' THEN COALESCE(pr.actual_odds,p.conservative_odds,p.original_odds)-1
                                       WHEN pr.result='lost' THEN -1 ELSE 0 END) AS units
                       FROM tipsters t JOIN picks p ON p.tipster_id=t.id
                       JOIN pick_results pr ON pr.pick_id=p.id
                       WHERE pr.result IN ('won','lost','push')
                         AND LOWER(COALESCE(p.conservative_market,p.original_market))=LOWER(?)
                       GROUP BY t.id""", (market,)).fetchall()
    weights = {}
    for row in rows:
        n = row["picks"]
        if n < 10:
            weights[row["tipster_id"]] = 0.85
            continue
        hit = (row["wins"] or 0) / n
        roi = (row["units"] or 0.0) / n
        raw = 1.0 + 0.75 * roi + 0.25 * (hit - 0.50)
        weights[row["tipster_id"]] = max(0.70, min(1.35, raw))
    return weights


def build_radar(limit: int = 20) -> dict:
    now = datetime.now(timezone.utc)
    with connect() as db:
        matches = db.execute("SELECT id, competition, home_team, away_team, kickoff, status FROM matches WHERE status='scheduled'").fetchall()
        picks = db.execute("SELECT p.*, t.name AS tipster_name, t.source AS tipster_source FROM picks p LEFT JOIN tipsters t ON t.id=p.tipster_id").fetchall()
        odds = db.execute("SELECT match_id, bookmaker, market, selection, odds, captured_at FROM odds").fetchall()
        weight_cache = {}
        pick_groups = defaultdict(list)
        odd_groups = defaultdict(list)
        for pick in picks: pick_groups[pick["match_id"]].append(pick)
        for odd in odds: odd_groups[odd["match_id"]].append(odd)
        candidates = []
        for match in matches:
            if _parse_time(match["kickoff"]) < now: continue
            match_picks = pick_groups[match["id"]]
            consensus = defaultdict(float)
            raw_count = defaultdict(int)
            for pick in match_picks:
                market = pick["conservative_market"] or pick["original_market"]
                selection = pick["conservative_selection"] or pick["original_selection"]
                key = (market.strip().lower(), selection.strip().lower())
                if market not in weight_cache: weight_cache[market] = _tipster_weights(db, market)
                consensus[key] += weight_cache[market].get(pick["tipster_id"], 1.0)
                raw_count[key] += 1
            for pick in match_picks:
                market = pick["conservative_market"] or pick["original_market"]
                selection = pick["conservative_selection"] or pick["original_selection"]
                probability = pick["probability"]
                confidence = pick["confidence"]
                model_probability = probability if probability is not None else confidence
                stored_odds = pick["conservative_odds"] or pick["original_odds"]
                if model_probability is None or stored_odds is None: continue
                key = (market.strip().lower(), selection.strip().lower())
                market_odds = [r["odds"] for r in odd_groups[match["id"]]
                               if r["market"].strip().lower() == market.strip().lower()
                               and r["selection"].strip().lower() == selection.strip().lower()]
                best_odds = max(market_odds, default=stored_odds)
                scored = score_opportunity(match_id=match["id"], match=f'{match["home_team"]} vs {match["away_team"]}',
                    market=market, selection=selection, odds=best_odds, model_probability=model_probability,
                    consensus=raw_count[key], confidence=confidence or model_probability)
                if scored.rating == "descartar": continue
                weighted_edge = scored.edge + min(0.02, max(0.0, consensus[key]-raw_count[key])*0.003)
                candidates.append({"match_id": scored.match_id, "match": scored.match, "competition": match["competition"],
                    "kickoff": match["kickoff"], "market": scored.market, "selection": scored.selection,
                    "odds": round(scored.odds,3), "model_probability": round(scored.model_probability,4),
                    "implied_probability": round(scored.implied_probability,4), "edge": round(scored.edge,4),
                    "weighted_edge": round(weighted_edge,4), "confidence": round(scored.confidence,4),
                    "consensus": raw_count[key], "consensus_weight": round(consensus[key],3), "rating": scored.rating,
                    "tipster": pick["tipster_name"], "source": pick["tipster_source"],
                    "probability_source": pick["probability_source"] or ("confidence_fallback" if probability is None else "model")})
    unique = {}
    for item in candidates:
        key = (item["match_id"], item["market"].lower(), item["selection"].lower())
        if key not in unique or item["weighted_edge"] > unique[key]["weighted_edge"]: unique[key] = item
    ranked = sorted(unique.values(), key=lambda x: (x["rating"]=="fuerte", x["weighted_edge"], x["consensus_weight"], x["model_probability"]), reverse=True)[:max(1,min(limit,100))]
    return {"generated_at": now.isoformat(), "count": len(ranked),
            "note": "Historial de tipsters pondera el consenso; requiere probabilidad calibrada y backtesting.",
            "opportunities": ranked}
