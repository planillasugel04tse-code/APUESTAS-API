from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Quote:
    bookmaker: str
    outcome: str
    price: float
    market_key: tuple[str, ...]
    limit: float | None = None
    changed_at: str | None = None
    bookmaker_changed_at: str | None = None
    main_line: bool | None = None
    suspended: bool = False


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 1.0 else None


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _outcome_name(selection: dict[str, Any]) -> str:
    for key in ("outcomeName", "outcome", "selectionName", "name", "label"):
        if selection.get(key) not in (None, ""):
            return str(selection[key]).strip()
    return str(selection.get("outcomeId", "unknown"))


def _canonical_outcome(name: str, *, participant1: str = "", participant2: str = "") -> str:
    text = _text(name)
    p1 = _text(participant1)
    p2 = _text(participant2)
    if text in {"1", "home", "local"} or (p1 and text == p1):
        return "home"
    if text in {"x", "draw", "tie", "empate"}:
        return "draw"
    if text in {"2", "away", "visitante", "visitor"} or (p2 and text == p2):
        return "away"
    if text in {"yes", "si", "sí"}:
        return "yes"
    if text == "no":
        return "no"
    if text.startswith("over") or text.startswith("más") or text.startswith("mas"):
        return "over"
    if text.startswith("under") or text.startswith("menos"):
        return "under"
    return text


def _market_key(market: dict[str, Any]) -> tuple[str, ...]:
    """Build a settlement-compatible market identity.

    Quotes from different periods/handicaps must never be combined into one
    theoretical surebet. Include the stable market identifiers when supplied
    and otherwise retain the descriptive settlement dimensions.
    """
    values = (
        market.get("marketId"),
        market.get("marketType"),
        market.get("marketName") or market.get("name"),
        market.get("period"),
        market.get("line", market.get("handicap")),
        market.get("playerProp"),
    )
    return tuple(_text(v) for v in values)


def _iter_bookmaker_markets(data: Any):
    if not isinstance(data, dict):
        return
    markets = data.get("markets") or data.get("bookmakerMarkets") or data.get("odds") or []
    if isinstance(markets, dict):
        markets = [markets]
    for market in markets:
        if not isinstance(market, dict):
            continue
        selections = market.get("selections") or market.get("outcomes") or market.get("odds") or []
        if isinstance(selections, dict):
            selections = [selections]
        for selection in selections:
            if not isinstance(selection, dict):
                continue
            price = _as_float(selection.get("price", selection.get("odds")))
            if price is None:
                continue
            yield _market_key(market), selection


def extract_quotes(payload: dict[str, Any]) -> tuple[list[Quote], dict[str, Any]]:
    """Normalize the common OddsPapi bookmakerOdds shape into comparable quotes."""
    bookmaker_odds = payload.get("bookmakerOdds") or payload.get("bookmakers") or {}
    if not isinstance(bookmaker_odds, dict):
        return [], payload

    p1 = str(payload.get("participant1Name") or payload.get("homeTeam") or "")
    p2 = str(payload.get("participant2Name") or payload.get("awayTeam") or "")
    quotes: list[Quote] = []
    for bookmaker, bookmaker_data in bookmaker_odds.items():
        active = bookmaker_data.get("bookmakerIsActive", True) if isinstance(bookmaker_data, dict) else True
        for market_key, selection in _iter_bookmaker_markets(bookmaker_data):
            if selection.get("suspended") is True or active is False:
                continue
            raw_name = _outcome_name(selection)
            outcome = _canonical_outcome(raw_name, participant1=p1, participant2=p2)
            quotes.append(
                Quote(
                    bookmaker=str(bookmaker),
                    outcome=outcome,
                    price=float(selection.get("price", selection.get("odds"))),
                    market_key=market_key,
                    limit=_as_float(selection.get("limit")),
                    changed_at=selection.get("changedAt") or selection.get("changed_at"),
                    bookmaker_changed_at=selection.get("bookmakerChangedAt") or selection.get("bookmaker_changed_at"),
                    main_line=selection.get("mainLine"),
                    suspended=bool(selection.get("suspended", False)),
                )
            )
    return quotes, {"participant1": p1, "participant2": p2}


def _best_by_outcome(
    quotes: list[Quote],
    allowed_bookmakers: set[str] | None = None,
    *,
    market_key: tuple[str, ...] | None = None,
) -> dict[str, Quote]:
    best: dict[str, Quote] = {}
    for quote in quotes:
        if allowed_bookmakers and quote.bookmaker.lower() not in allowed_bookmakers:
            continue
        if market_key is not None and quote.market_key != market_key:
            continue
        current = best.get(quote.outcome)
        if current is None or quote.price > current.price:
            best[quote.outcome] = quote
    return best


def _candidate_market_keys(quotes: list[Quote]) -> list[tuple[str, ...]]:
    return list(dict.fromkeys(q.market_key for q in quotes))


def analyze_odds_payload(
    payload: dict[str, Any],
    *,
    bankroll: float = 100.0,
    execution_bookmakers: list[str] | None = None,
    reference_bookmakers: list[str] | None = None,
) -> dict[str, Any]:
    """Calculate arbitrage and reference price deltas from one OddsPapi response."""
    quotes, meta = extract_quotes(payload)
    execution = {x.lower().strip() for x in (execution_bookmakers or []) if x.strip()}
    references = {x.lower().strip() for x in (reference_bookmakers or []) if x.strip()}

    opportunities: list[dict[str, Any]] = []
    outcomes_sets = ({"home", "draw", "away"}, {"home", "away"}, {"yes", "no"}, {"over", "under"})
    for market_key in _candidate_market_keys(quotes):
        best = _best_by_outcome(quotes, execution or None, market_key=market_key)
        for required in outcomes_sets:
            if not required.issubset(best):
                continue
            selected = {key: best[key] for key in required}
            implied_sum = sum(1.0 / q.price for q in selected.values())
            if implied_sum >= 1:
                continue
            stakes = {
                key: round(bankroll * (1.0 / quote.price) / implied_sum, 2)
                for key, quote in selected.items()
            }
            # Rounding can leave a cent-level residual; place it on the first leg.
            residual = round(bankroll - sum(stakes.values()), 2)
            first_key = next(iter(stakes))
            stakes[first_key] = round(stakes[first_key] + residual, 2)
            opportunities.append({
                "type": "surebet",
                "market_key": market_key,
                "outcomes": {
                    key: {
                        "bookmaker": quote.bookmaker,
                        "odds": quote.price,
                        "stake": stakes[key],
                        "limit": quote.limit,
                        "changed_at": quote.changed_at,
                        "bookmaker_changed_at": quote.bookmaker_changed_at,
                        "main_line": quote.main_line,
                    }
                    for key, quote in selected.items()
                },
                "implied_sum": round(implied_sum, 8),
                "profit_margin": round((1.0 / implied_sum) - 1.0, 6),
                "profit_percent": round(((1.0 / implied_sum) - 1.0) * 100, 3),
                "bankroll": bankroll,
                "execution_scope": sorted(execution),
            })
            break

    edge_rows: list[dict[str, Any]] = []
    if references:
        for market_key in _candidate_market_keys(quotes):
            best = _best_by_outcome(quotes, execution or None, market_key=market_key)
            reference_best = _best_by_outcome(quotes, references, market_key=market_key)
            for outcome, exec_quote in best.items():
                ref = reference_best.get(outcome)
                if ref is None:
                    continue
                edge_rows.append({
                    "outcome": outcome,
                    "execution_bookmaker": exec_quote.bookmaker,
                    "execution_odds": exec_quote.price,
                    "reference_bookmaker": ref.bookmaker,
                    "reference_odds": ref.price,
                    "edge_percent": round((exec_quote.price / ref.price - 1.0) * 100, 3),
                    "market_key": market_key,
                    "metric": "price_delta_vs_reference",
                })

    return {
        "fixture_id": payload.get("fixtureId"),
        "match": f"{meta['participant1']} vs {meta['participant2']}".strip(" vs"),
        "has_odds": bool(payload.get("hasOdds", quotes)),
        "quotes_seen": len(quotes),
        "surebets": opportunities,
        "markets_checked": len(_candidate_market_keys(quotes)),
        "reference_edge": edge_rows,
        "execution_bookmakers": sorted(execution),
        "reference_bookmakers": sorted(references),
    }
