from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .db import connect
from .value_engine import value_signal


@dataclass(frozen=True)
class RadarValue:
    match_id: int
    match: str
    competition: str
    market: str
    selection: str
    line: float | None
    odds: float
    fair_probability: float
    fair_odds: float
    edge: float
    ev: float
    bookmakers: int
    consensus: int
    rating: str


def build_value_radar(limit: int = 20) -> dict:
    with connect() as db:
        rows = db.execute("""
            SELECT o.match_id, m.competition, m.home_team, m.away_team,
                   o.bookmaker, o.market, o.selection, o.line, o.odds
            FROM odds o
            JOIN matches m ON m.id=o.match_id
            WHERE m.status='scheduled' AND o.odds > 1
        """).fetchall()

    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        key = (row["match_id"], row["market"].lower(), row["line"], row["selection"].lower())
        groups[key].append(row)

    markets: dict[tuple, dict[str, float]] = defaultdict(dict)
    metadata: dict[tuple, object] = {}
    for key, items in groups.items():
        match_id, market, line, selection = key
        best = max(items, key=lambda r: r["odds"])
        market_key = (match_id, market, line)
        markets[market_key][selection] = max(markets[market_key].get(selection, 0.0), float(best["odds"]))
        metadata[market_key] = best

    candidates: list[dict] = []
    for market_key, selections in markets.items():
        if len(selections) < 2:
            continue
        names = list(selections)
        prices = [selections[n] for n in names]
        implied = [1 / p for p in prices]
        total = sum(implied)
        if total <= 0:
            continue
        fair_probs = [p / total for p in implied]
        for name, offered, probability in zip(names, prices, fair_probs):
            signal = value_signal(offered, probability, name)
            if signal.edge < 0.03:
                continue
            items = groups.get((market_key[0], market_key[1], market_key[2], name), [])
            bookmakers = len({r["bookmaker"] for r in items})
            candidates.append({
                "match_id": market_key[0],
                "match": f"{metadata[market_key]['home_team']} vs {metadata[market_key]['away_team']}",
                "competition": metadata[market_key]["competition"],
                "market": metadata[market_key]["market"],
                "selection": name,
                "line": market_key[2],
                "odds": round(offered, 3),
                "fair_probability": round(probability, 4),
                "fair_odds": round(signal.fair_odds, 3),
                "edge": round(signal.edge, 4),
                "ev": round(signal.ev, 4),
                "bookmakers": bookmakers,
                "consensus": len(names),
                "rating": signal.rating,
            })

    ranked = sorted(candidates, key=lambda x: (x["edge"], x["bookmakers"], x["consensus"]), reverse=True)[: max(1, min(limit, 100))]
    return {
        "count": len(ranked),
        "note": "Radar de value basado únicamente en cuotas almacenadas; no sustituye una probabilidad calibrada propia.",
        "opportunities": ranked,
    }
