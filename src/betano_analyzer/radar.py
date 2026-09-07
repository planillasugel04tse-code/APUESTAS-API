from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .db import connect
from .opportunities import score_opportunity


def _parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_radar(limit: int = 20) -> dict:
    now = datetime.now(timezone.utc)
    with connect() as db:
        matches = db.execute(
            "SELECT id, competition, home_team, away_team, kickoff, status "
            "FROM matches WHERE status = 'scheduled'"
        ).fetchall()
        picks = db.execute(
            "SELECT p.*, t.name AS tipster_name, t.source AS tipster_source "
            "FROM picks p LEFT JOIN tipsters t ON t.id = p.tipster_id"
        ).fetchall()
        odds = db.execute(
            "SELECT match_id, bookmaker, market, selection, odds, captured_at FROM odds"
        ).fetchall()

    pick_groups = defaultdict(list)
    for pick in picks:
        pick_groups[pick["match_id"]].append(pick)

    odd_groups = defaultdict(list)
    for odd in odds:
        odd_groups[odd["match_id"]].append(odd)

    candidates = []
    for match in matches:
        kickoff = _parse_time(match["kickoff"])
        if kickoff < now:
            continue

        match_picks = pick_groups[match["id"]]
        if not match_picks:
            continue

        consensus = defaultdict(int)
        for pick in match_picks:
            selection = pick["conservative_selection"] or pick["original_selection"]
            market = pick["conservative_market"] or pick["original_market"]
            consensus[(market.strip().lower(), selection.strip().lower())] += 1

        for pick in match_picks:
            market = pick["conservative_market"] or pick["original_market"]
            selection = pick["conservative_selection"] or pick["original_selection"]
            confidence = pick["confidence"]
            stored_odds = pick["conservative_odds"] or pick["original_odds"]
            if confidence is None or stored_odds is None:
                continue

            key = (market.strip().lower(), selection.strip().lower())
            consensus_count = consensus[key]
            market_odds = [
                row["odds"] for row in odd_groups[match["id"]]
                if row["market"].strip().lower() == market.strip().lower()
                and row["selection"].strip().lower() == selection.strip().lower()
            ]
            best_odds = max(market_odds, default=stored_odds)
            scored = score_opportunity(
                match_id=match["id"],
                match=f'{match["home_team"]} vs {match["away_team"]}',
                market=market,
                selection=selection,
                odds=best_odds,
                model_probability=confidence,
                consensus=consensus_count,
                confidence=confidence,
            )
            if scored.rating == "descartar":
                continue
            candidates.append({
                "match_id": scored.match_id,
                "match": scored.match,
                "competition": match["competition"],
                "kickoff": match["kickoff"],
                "market": scored.market,
                "selection": scored.selection,
                "odds": round(scored.odds, 3),
                "model_probability": round(scored.model_probability, 4),
                "implied_probability": round(scored.implied_probability, 4),
                "edge": round(scored.edge, 4),
                "confidence": round(scored.confidence, 4),
                "consensus": scored.consensus,
                "rating": scored.rating,
                "tipster": pick["tipster_name"],
                "source": pick["tipster_source"],
            })

    # Deduplicate the same market/selection for a match, keeping the strongest edge.
    unique = {}
    for item in candidates:
        key = (item["match_id"], item["market"].lower(), item["selection"].lower())
        if key not in unique or item["edge"] > unique[key]["edge"]:
            unique[key] = item

    ranked = sorted(
        unique.values(),
        key=lambda item: (item["rating"] == "fuerte", item["edge"], item["consensus"], item["confidence"]),
        reverse=True,
    )[: max(1, min(limit, 100))]

    return {
        "generated_at": now.isoformat(),
        "count": len(ranked),
        "note": "Filtro inicial; requiere datos calibrados y backtesting antes de usar dinero real.",
        "opportunities": ranked,
    }
