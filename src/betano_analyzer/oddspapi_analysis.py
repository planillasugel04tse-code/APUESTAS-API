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
    try: result = float(value)
    except (TypeError, ValueError): return None
    return result if result > 1 else None

def _text(value: Any) -> str: return " ".join(str(value or "").strip().lower().split())

def _outcome_name(value: Any) -> str:
    if isinstance(value, dict): value = value.get("outcomeName") or value.get("name") or value.get("outcome") or value.get("selection") or value.get("label")
    return _text(value)

def _canonical_outcome(value: Any) -> str:
    text = _outcome_name(value)
    if text in {"home", "1", "local", "home team"}: return "home"
    if text in {"draw", "x", "tie", "empate"}: return "draw"
    if text in {"away", "2", "visitor", "visitante", "away team"}: return "away"
    if text in {"yes", "si", "sí"}: return "yes"
    if text == "no": return "no"
    if text.startswith("over") or text.startswith("más de") or text.startswith("mas de"): return "over"
    if text.startswith("under") or text.startswith("menos de"): return "under"
    return text

def _market_key(market: dict[str, Any]) -> tuple[str, ...]:
    return (str(market.get("marketId") or ""), _text(market.get("marketType") or market.get("type")), _text(market.get("marketName") or market.get("name")), _text(market.get("period")), str(market.get("line") if market.get("line") is not None else market.get("handicap") or ""), _text(market.get("playerProp")))

def _iter_bookmaker_markets(bookmaker: dict[str, Any]):
    markets = bookmaker.get("markets") or bookmaker.get("bookmakerMarkets") or bookmaker.get("odds") or []
    if isinstance(markets, dict): markets = [markets]
    for market in markets:
        if isinstance(market, dict): yield market

def extract_quotes(payload: dict[str, Any]) -> tuple[list[Quote], dict[str, Any]]:
    quotes: list[Quote] = []; bookmakers = payload.get("bookmakerOdds") or payload.get("bookmakers") or []
    if isinstance(bookmakers, dict): bookmakers = [bookmakers]
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, dict): continue
        name = str(bookmaker.get("bookmakerName") or bookmaker.get("name") or bookmaker.get("slug") or "").strip()
        if not name: continue
        for market in _iter_bookmaker_markets(bookmaker):
            key = _market_key(market); outcomes = market.get("outcomes") or market.get("selections") or []
            if isinstance(outcomes, dict): outcomes = [outcomes]
            for outcome in outcomes:
                if not isinstance(outcome, dict): continue
                price = _as_float(outcome.get("price") or outcome.get("odds"))
                if price is None or bool(outcome.get("suspended", market.get("suspended", False))): continue
                quotes.append(Quote(name, _canonical_outcome(outcome), price, key, outcome.get("limit", market.get("limit")), outcome.get("changedAt") or market.get("changedAt") or bookmaker.get("changedAt"), bookmaker.get("bookmakerChangedAt") or bookmaker.get("changedAt"), outcome.get("mainLine", market.get("mainLine"))))
    return quotes, {"participant1": payload.get("participant1") or payload.get("home") or "", "participant2": payload.get("participant2") or payload.get("away") or ""}

def _best_by_outcome(quotes: list[Quote], allowed_bookmakers: set[str] | None = None, *, market_key: tuple[str, ...] | None = None) -> dict[str, Quote]:
    best: dict[str, Quote] = {}
    for quote in quotes:
        if allowed_bookmakers is not None and quote.bookmaker.lower() not in allowed_bookmakers: continue
        if market_key is not None and quote.market_key != market_key: continue
        current = best.get(quote.outcome)
        if current is None or quote.price > current.price: best[quote.outcome] = quote
    return best

def _candidate_market_keys(quotes: list[Quote]) -> list[tuple[str, ...]]: return list(dict.fromkeys(q.market_key for q in quotes))

def analyze_odds_payload(payload: dict[str, Any], *, bankroll: float = 100.0, execution_bookmakers: list[str] | None = None, reference_bookmakers: list[str] | None = None) -> dict[str, Any]:
    quotes, meta = extract_quotes(payload); execution = {x.lower().strip() for x in (execution_bookmakers or []) if x.strip()}; references = {x.lower().strip() for x in (reference_bookmakers or []) if x.strip()}; opportunities = []
    for market_key in _candidate_market_keys(quotes):
        best = _best_by_outcome(quotes, execution, market_key=market_key)
        for required in ({"home", "draw", "away"}, {"home", "away"}, {"yes", "no"}, {"over", "under"}):
            if not required.issubset(best): continue
            selected = {key: best[key] for key in required}
            if len({q.bookmaker.lower() for q in selected.values()}) < 2: continue
            implied_sum = sum(1.0 / q.price for q in selected.values())
            if implied_sum >= 1: continue
            stakes = {key: round(bankroll * (1.0 / q.price) / implied_sum, 2) for key,q in selected.items()}; first = next(iter(stakes)); stakes[first] = round(stakes[first] + round(bankroll-sum(stakes.values()),2), 2)
            opportunities.append({"type":"surebet","market_key":market_key,"outcomes":{key:{"bookmaker":q.bookmaker,"odds":q.price,"stake":stakes[key],"limit":q.limit,"changed_at":q.changed_at,"bookmaker_changed_at":q.bookmaker_changed_at,"main_line":q.main_line} for key,q in selected.items()},"implied_sum":round(implied_sum,8),"profit_margin":round(1/implied_sum-1,6),"profit_percent":round((1/implied_sum-1)*100,3),"bankroll":bankroll,"execution_scope":sorted(execution)}); break
    edge_rows=[]
    if references:
        for market_key in _candidate_market_keys(quotes):
            best=_best_by_outcome(quotes, execution, market_key=market_key); reference_best=_best_by_outcome(quotes, references, market_key=market_key)
            for outcome,exec_quote in best.items():
                ref=reference_best.get(outcome)
                if ref is not None: edge_rows.append({"outcome":outcome,"execution_bookmaker":exec_quote.bookmaker,"execution_odds":exec_quote.price,"reference_bookmaker":ref.bookmaker,"reference_odds":ref.price,"edge_percent":round((exec_quote.price/ref.price-1)*100,3),"market_key":market_key,"metric":"price_delta_vs_reference"})
    return {"fixture_id":payload.get("fixtureId"),"match":f"{meta['participant1']} vs {meta['participant2']}".strip(" vs"),"has_odds":bool(payload.get("hasOdds",quotes)),"quotes_seen":len(quotes),"surebets":opportunities,"markets_checked":len(_candidate_market_keys(quotes)),"reference_edge":edge_rows,"execution_bookmakers":sorted(execution),"reference_bookmakers":sorted(references)}
