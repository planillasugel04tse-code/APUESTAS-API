from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .db import connect
from .peru_bookmakers import PERU_BOOKMAKER_CANDIDATES, PERU_BOOKMAKER_REGISTRY, SUREBET_EXTRA_BOOKMAKERS

PERU_LEAGUE_KEYWORDS = ("liga 1", "liga 2", "liga 3", "liga femenina", "liga femenina peru", "copa peru", "copa perú", "primera division peru", "primera división peru", "segunda division peru", "segunda división peru", "liga peruana", "torneo peruano")
TARGET_PROFITS = (250, 500, 1000, 3000)

@dataclass(frozen=True)
class Arbitrage:
    match_id: int
    match: str
    market: str
    line: float | None
    outcomes: dict[str, dict[str, object]]
    implied_sum: float
    profit_margin: float
    mode: str
    competition: str = ""
    scope: str = "world"
    bookmaker_mix: str = ""
    total_stake: int | None = None
    total_return: int | None = None
    guaranteed_profit: int | None = None
    roi_percent: float | None = None
    target_profits: dict[int, dict[str, object]] | None = None


def _integer_stake_plan(outcomes: dict[str, dict[str, object]], target_profit: int) -> dict[str, object]:
    """Find integer stakes whose guaranteed profit is at least target_profit."""
    if target_profit <= 0 or not outcomes:
        raise ValueError("target_profit must be positive and outcomes cannot be empty")
    odds = {key: float(value["odds"]) for key, value in outcomes.items()}
    if any(price <= 1 for price in odds.values()):
        raise ValueError("all odds must be > 1")
    implied_sum = sum(1.0 / price for price in odds.values())
    if implied_sum >= 1:
        raise ValueError("not a surebet")
    ideal_total = target_profit / ((1.0 / implied_sum) - 1.0)
    total = max(1, int(ideal_total))
    while True:
        ideal = {key: total * (1.0 / price) / implied_sum for key, price in odds.items()}
        stakes = {key: max(1, int(round(value))) for key, value in ideal.items()}
        diff = total - sum(stakes.values())
        if diff > 0:
            for key in sorted(stakes, key=lambda key: ideal[key] - stakes[key], reverse=True)[:diff]:
                stakes[key] += 1
        elif diff < 0:
            for key in sorted(stakes, key=lambda key: ideal[key] - stakes[key])[:abs(diff)]:
                if stakes[key] > 1:
                    stakes[key] -= 1
        actual_total = sum(stakes.values())
        returns = {key: int(stakes[key] * odds[key]) for key in stakes}
        guaranteed_return = min(returns.values())
        guaranteed_profit = guaranteed_return - actual_total
        if guaranteed_profit >= target_profit:
            return {
                "stakes": stakes,
                "total_stake": actual_total,
                "total_return": guaranteed_return,
                "guaranteed_profit": guaranteed_profit,
                "roi_percent": (guaranteed_profit / actual_total) * 100,
                "implied_sum": implied_sum,
            }
        total += 1


def calculate_stakes(outcomes: dict[str, dict[str, object]], total_stake: float) -> dict[str, object]:
    """Return an integer-stake plan for a fixed bankroll."""
    if total_stake <= 0 or not outcomes:
        raise ValueError("total_stake must be positive and outcomes cannot be empty")
    odds = {key: float(value["odds"]) for key, value in outcomes.items()}
    if any(price <= 1 for price in odds.values()):
        raise ValueError("all odds must be > 1")
    implied_sum = sum(1.0 / price for price in odds.values())
    if implied_sum >= 1:
        raise ValueError("not a surebet")
    total = max(1, int(round(total_stake)))
    ideal = {key: total * (1.0 / price) / implied_sum for key, price in odds.items()}
    stakes = {key: max(1, int(round(value))) for key, value in ideal.items()}
    diff = total - sum(stakes.values())
    if diff > 0:
        for key in sorted(stakes, key=lambda k: ideal[k] - stakes[k], reverse=True)[:diff]:
            stakes[key] += 1
    elif diff < 0:
        for key in sorted(stakes, key=lambda k: ideal[k] - stakes[k])[:abs(diff)]:
            if stakes[key] > 1:
                stakes[key] -= 1
    actual_total = sum(stakes.values())
    guaranteed_return = min(int(stakes[key] * odds[key]) for key in stakes)
    profit = guaranteed_return - actual_total
    return {
        "stakes": stakes,
        "total_stake": actual_total,
        "total_return": guaranteed_return,
        "guaranteed_profit": profit,
        "roi_percent": (profit / actual_total) * 100,
        "implied_sum": implied_sum,
    }


def build_target_profit_plans(outcomes: dict[str, dict[str, object]], targets: tuple[int, ...] = TARGET_PROFITS) -> dict[int, dict[str, object]]:
    """Build the four requested target-profit plans only."""
    return {target: _integer_stake_plan(outcomes, target) for target in targets}


def _live_stale_minutes() -> int:
    try:
        return max(1, int(os.getenv("LIVE_STALE_MINUTES", "15")))
    except (TypeError, ValueError):
        return 15


def _is_live(kickoff: object, now: datetime | None = None, status: object | None = None) -> bool:
    status_key = str(status or "").strip().lower()
    if status_key in {"live", "in_play", "inplay", "started"}:
        return True
    if status_key in {"scheduled", "pre_match", "prematch", "upcoming", "finished", "ended", "cancelled", "canceled", "postponed"}:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        value = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
        value = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return value <= now
    except (TypeError, ValueError):
        return False


def _market_base(market: object) -> str:
    text = str(market or "").lower()
    for suffix in ("_ft", "_1h", "_2h"):
        if text.endswith(suffix):
            return text[:-len(suffix)]
    return text


def _selection_key(selection: object) -> str:
    return str(selection or "").strip().lower().split(":", 1)[-1].strip()


def _captured_at(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_stale_live(value: object, now: datetime, stale_minutes: int) -> bool:
    timestamp = _captured_at(value)
    return timestamp is None or (now - timestamp) > timedelta(minutes=stale_minutes)


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _normalize_bookmaker(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isalnum())

PERU_BOOKMAKER_KEYS = frozenset(_normalize_bookmaker(value) for row in PERU_BOOKMAKER_REGISTRY for value in (row.get("brand"), row.get("domain"), row.get("oddspapi_slug")))
CANDIDATE_BOOKMAKER_KEYS = frozenset(_normalize_bookmaker(value) for row in PERU_BOOKMAKER_CANDIDATES for value in (row.get("brand"), row.get("domain"), row.get("oddspapi_slug")))
INTERNATIONAL_EXTRA_KEYS = frozenset(_normalize_bookmaker(value) for value in SUREBET_EXTRA_BOOKMAKERS)


def classify_bookmaker(bookmaker: object) -> str:
    """Classify known Peru books as PERU; every other discovered book is international.

    OddsPapi is dynamic, so the world engine must not be limited to a hard-coded
    international allow-list. Candidate Peru names remain UNKNOWN so they cannot
    accidentally qualify as Peru until explicitly verified.
    """
    key = _normalize_bookmaker(bookmaker)
    if key in PERU_BOOKMAKER_KEYS:
        return "PERU"
    if key in CANDIDATE_BOOKMAKER_KEYS:
        return "UNKNOWN"
    if key in INTERNATIONAL_EXTRA_KEYS:
        return "INTERNATIONAL"
    return "INTERNATIONAL"


def _is_peru_bookmaker(bookmaker: object) -> bool:
    return classify_bookmaker(bookmaker) == "PERU"


def _world_bookmaker_mix(selected: dict[str, tuple[str, float]]) -> str:
    classes = {classify_bookmaker(value[0]) for value in selected.values()}
    if "UNKNOWN" in classes:
        return "UNKNOWN"
    if classes == {"PERU"}:
        return "PERU + PERU"
    if classes == {"INTERNATIONAL"}:
        return "INTERNATIONAL + INTERNATIONAL"
    if classes == {"PERU", "INTERNATIONAL"}:
        return "PERU + INTERNATIONAL"
    return "UNKNOWN"


def _valid_world_bookmaker_mix(selected: dict[str, tuple[str, float]]) -> bool:
    if len({quote[0] for quote in selected.values()}) < 2:
        return False
    return _world_bookmaker_mix(selected) in {"PERU + INTERNATIONAL", "INTERNATIONAL + INTERNATIONAL"}


def _is_peru_competition(competition: object) -> bool:
    text = _normalize_text(competition)
    return any(keyword in text for keyword in PERU_LEAGUE_KEYWORDS)


def _scope_for_competition(competition: object) -> str:
    return "peru" if _is_peru_competition(competition) else "world"


def _scope_matches(scope: str, competition: object) -> bool:
    normalized = str(scope or "all").strip().lower()
    if normalized not in {"all", "peru", "world"}:
        raise ValueError("scope must be one of: all, peru, world")
    return normalized == "all" or _scope_for_competition(competition) == normalized


def _league_matches(league: str | None, competition: object) -> bool:
    return not league or _normalize_text(league) in _normalize_text(competition)


def find_arbitrage(limit: int = 100, *, live: bool = False, match_id: int | None = None, scope: str = "all", league: str | None = None, total_stake: float | None = None) -> list[Arbitrage]:
    normalized_scope = str(scope or "all").strip().lower()
    if normalized_scope not in {"all", "peru", "world"}:
        raise ValueError("scope must be one of: all, peru, world")
    now = datetime.now(timezone.utc)
    stale_minutes = _live_stale_minutes()
    with connect() as db:
        rows = db.execute("""SELECT o.match_id,o.bookmaker,o.market,o.selection,o.line,o.odds,o.captured_at,m.home_team,m.away_team,m.kickoff,m.status,m.competition FROM odds o JOIN matches m ON m.id=o.match_id WHERE o.odds > 1 AND (? IS NULL OR o.match_id = ?) ORDER BY o.captured_at DESC""", (match_id, match_id)).fetchall()
    latest = {}
    for row in rows:
        competition = row["competition"] or ""
        if not _scope_matches(normalized_scope, competition) or not _league_matches(league, competition):
            continue
        if _is_live(row["kickoff"], now, row["status"]) != live:
            continue
        if live and _is_stale_live(row["captured_at"], now, stale_minutes):
            continue
        key = (row["match_id"], str(row["market"]).lower(), row["line"], str(row["bookmaker"]).lower(), _selection_key(row["selection"]))
        current = latest.get(key)
        if current is None:
            latest[key] = row
            continue
        current_time = _captured_at(current["captured_at"])
        row_time = _captured_at(row["captured_at"])
        if row_time is not None and (current_time is None or row_time > current_time):
            latest[key] = row
    groups = defaultdict(list)
    for row in latest.values():
        groups[(row["match_id"], row["market"], row["line"])].append(row)
    result = []
    for (current_match_id, market, line), quotes in groups.items():
        best = {}
        for row in quotes:
            outcome = _selection_key(row["selection"])
            price = float(row["odds"])
            if outcome not in best or price > best[outcome][1]:
                best[outcome] = (row["bookmaker"], price)
        base_market = _market_base(market)
        if base_market == "1x2":
            required = {"home", "draw", "away"}
        elif base_market in {"goals", "corners", "cards"}:
            required = {"over", "under"}
        elif base_market == "btts":
            required = {"yes", "no"}
        elif base_market in {"spread", "handicap", "asian_handicap"}:
            required = {"home", "away"}
        else:
            continue
        if not required.issubset(best):
            continue
        selected = {key: best[key] for key in required}
        mix = _world_bookmaker_mix(selected)
        if normalized_scope == "peru" and any(classify_bookmaker(q[0]) != "PERU" for q in selected.values()):
            continue
        if normalized_scope == "world" and not _valid_world_bookmaker_mix(selected):
            continue
        implied_sum = sum(1.0 / quote[1] for quote in selected.values())
        if implied_sum >= 1.0:
            continue
        competition = quotes[0]["competition"] or ""
        stake_data = calculate_stakes({key: {"odds": quote[1]} for key, quote in selected.items()}, total_stake) if total_stake else None
        target_data = build_target_profit_plans({key: {"odds": quote[1]} for key, quote in selected.items()})
        result.append(Arbitrage(
            match_id=current_match_id,
            match=f"{quotes[0]['home_team']} vs {quotes[0]['away_team']}",
            market=market,
            line=line,
            outcomes={key: {"bookmaker": quote[0], "odds": quote[1], "classification": classify_bookmaker(quote[0])} for key, quote in selected.items()},
            implied_sum=implied_sum,
            profit_margin=(1.0 / implied_sum) - 1.0,
            mode="live" if live else "pre_match",
            competition=competition,
            scope="peru" if normalized_scope == "peru" else _scope_for_competition(competition),
            bookmaker_mix=mix,
            total_stake=stake_data["total_stake"] if stake_data else None,
            total_return=stake_data["total_return"] if stake_data else None,
            guaranteed_profit=stake_data["guaranteed_profit"] if stake_data else None,
            roi_percent=stake_data["roi_percent"] if stake_data else None,
            target_profits=target_data,
        ))
        if len(result) >= limit:
            break
    return result
