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


def _consensus_fair_probabilities(rows: list, excluded_bookmaker: str) -> dict[str, float]:
    """De-vig each reference book, then average its fair probabilities."""
    by_book: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        book = str(row["bookmaker"])
        if book.lower() == excluded_bookmaker.lower():
            continue
        by_book[book][str(row["selection"]).lower()] = float(row["odds"])

    fair_samples: dict[str, list[float]] = defaultdict(list)
    for prices in by_book.values():
        implied = {name: 1 / price for name, price in prices.items() if price > 1}
        if len(implied) < 2:
            continue
        total = sum(implied.values())
        for name, probability in implied.items():
            fair_samples[name].append(probability / total)

    consensus = {name: sum(values) / len(values) for name, values in fair_samples.items()}
    total = sum(consensus.values())
    return {name: probability / total for name, probability in consensus.items()} if total > 0 else {}


def build_value_radar(limit: int = 20, offered_bookmaker: str = "Betano") -> dict:
    with connect() as db:
        rows = db.execute("""
            SELECT o.match_id, m.competition, m.home_team, m.away_team,
                   o.bookmaker, o.market, o.selection, o.line, o.odds
            FROM odds o JOIN matches m ON m.id=o.match_id
            WHERE m.status='scheduled' AND o.odds > 1
        """).fetchall()

    market_rows: dict[tuple, list] = defaultdict(list)
    for row in rows:
        market_rows[(row["match_id"], row["market"].lower(), row["line"])].append(row)

    candidates: list[dict] = []
    for market_key, items in market_rows.items():
        fair = _consensus_fair_probabilities(items, offered_bookmaker)
        if len(fair) < 2:
            continue
        offered = [r for r in items if str(r["bookmaker"]).lower() == offered_bookmaker.lower()]
        best: dict[str, object] = {}
        for row in offered:
            selection = str(row["selection"]).lower()
            if selection in fair and (selection not in best or row["odds"] > best[selection]["odds"]):
                best[selection] = row
        for selection, row in best.items():
            signal = value_signal(float(row["odds"]), fair[selection], selection)
            if signal.edge < 0.03:
                continue
            books = len({str(r["bookmaker"]) for r in items if str(r["selection"]).lower() == selection})
            candidates.append({
                "match_id": market_key[0], "match": f"{row['home_team']} vs {row['away_team']}",
                "competition": row["competition"], "market": row["market"], "selection": selection,
                "line": market_key[2], "bookmaker": offered_bookmaker, "odds": round(float(row["odds"]), 3),
                "fair_probability": round(fair[selection], 4), "fair_odds": round(signal.fair_odds, 3),
                "edge": round(signal.edge, 4), "ev": round(signal.ev, 4), "bookmakers": books,
                "consensus": len(fair), "rating": signal.rating,
            })

    ranked = sorted(candidates, key=lambda x: (x["edge"], x["bookmakers"], x["consensus"]), reverse=True)[:max(1, min(limit, 100))]
    return {"count": len(ranked), "offered_bookmaker": offered_bookmaker,
            "note": "Value contra consenso multi-casa sin margen; Betano se excluye del fair price.",
            "opportunities": ranked}
