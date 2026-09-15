from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .db import connect
from .peru_bookmakers import PERU_BOOKMAKER_CANDIDATES, PERU_BOOKMAKER_REGISTRY, SUREBET_EXTRA_BOOKMAKERS

PERU_LEAGUE_KEYWORDS = ("liga 1", "liga 2", "liga 3", "liga femenina", "liga femenina peru", "copa peru", "copa perú", "primera division peru", "primera división peru", "segunda division peru", "segunda división peru", "liga peruana", "torneo peruano")

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
    roi_percent: int | None = None
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
        order = sorted(stakes, key=lambda key: ideal[key] - stakes[key], reverse=diff > 0)
        step = 1 if diff > 0 else -1
        for key in order[:abs(diff)]:
            if step > 0 or stakes[key] > 1:
                stakes[key] += step
        actual_total = sum(stakes.values())
        returns = {key: int(stakes[key] * odds[key]) for key in stakes}
        guaranteed_return = min(returns.values())
        guaranteed_profit = guaranteed_return - actual_total
        if guaranteed_profit >= target_profit:
            roi = int((guaranteed_profit / actual_total) * 100)
            return {"stakes": stakes, "total_stake": actual_total, "total_return": guaranteed_return, "guaranteed_profit": guaranteed_profit, "roi_percent": roi, "implied_sum": implied_sum}
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
        for key in sorted(stakes, key=lambda k: ideal[k] - stakes[k], reverse=True)[:diff]: stakes[key] += 1
    elif diff < 0:
        for key in sorted(stakes, key=lambda k: ideal[k] - stakes[k])[:abs(diff)]:
            if stakes[key] > 1: stakes[key] -= 1
    actual_total = sum(stakes.values())
    guaranteed_return = min(int(stakes[key] * odds[key]) for key in stakes)
    profit = guaranteed_return - actual_total
    return {"stakes": stakes, "total_stake": actual_total, "total_return": guaranteed_return, "guaranteed_profit": profit, "roi_percent": int((profit / actual_total) * 100), "implied_sum": implied_sum}


def build_target_profit_plans(outcomes: dict[str, dict[str, object]], targets: tuple[int, ...] = (250, 500, 1000, 3000, 5000)) -> dict[int, dict[str, object]]:
    return {target: _integer_stake_plan(outcomes, target) for target in targets}


def _live_stale_minutes() -> int:
    try: return max(1, int(os.getenv("LIVE_STALE_MINUTES", "15")))
    except (TypeError, ValueError): return 15


def _is_live(kickoff: object, now: datetime | None = None, status: object | None = None) -> bool:
    status_key = str(status or "").strip().lower()
    if status_key in {"live", "in_play", "inplay", "started"}: return True
    if status_key in {"scheduled", "pre_match", "prematch", "upcoming"}: return False
    if status_key in {"finished", "ended", "cancelled", "canceled", "postponed"}: return False
    now = now or datetime.now(timezone.utc)
    try:
        value = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
        if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
        return value <= now
    except (TypeError, ValueError): return False


def _market_base(market: object) -> str:
    text = str(market or "").lower()
    for suffix in ("_ft", "_1h", "_2h"):
        if text.endswith(suffix): return text[:-len(suffix)]
    return text


def _selection_key(selection: object) -> str:
    return str(selection or "").strip().lower().split(":", 1)[-1].strip()


def _captured_at(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError): return None


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
    key = _normalize_bookmaker(bookmaker)
    if key in PERU_BOOKMAKER_KEYS: return "PERU"
    if key in INTERNATIONAL_EXTRA_KEYS: return "INTERNATIONAL"
    if key in CANDIDATE_BOOKMAKER_KEYS: return "UNKNOWN"
    return "UNKNOWN"


def _is_peru_bookmaker(bookmaker: object) -> bool:
    """Backward-compatible predicate backed by the canonical Peru registry."""
    return classify_bookmaker(bookmaker) == "PERU"


def _world_bookmaker_mix(selected: dict[str, tuple[str, float]]) -> str:
    classes = {classify_bookmaker(value[0]) for value in selected.values()}
    if "UNKNOWN" in classes: return "UNKNOWN"
    if classes == {"PERU"}: return "PERU + PERU"
    if classes == {"INTERNATIONAL"}: return "INTERNATIONAL + INTERNATIONAL"
    if classes == {"PERU", "INTERNATIONAL"}: return "PERU + INTERNATIONAL"
    return "UNKNOWN"


def _valid_world_bookmaker_mix(selected: dict[str, tuple[str, float]]) -> bool:
    return _world_bookmaker_mix(selected) in {"PERU + INTERNATIONAL", "INTERNATIONAL + INTERNATIONAL"}
