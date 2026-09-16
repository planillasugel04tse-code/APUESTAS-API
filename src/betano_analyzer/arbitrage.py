from __future__ import annotations

import itertools
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .db import connect
from .peru_bookmakers import PERU_BOOKMAKER_CANDIDATES, PERU_BOOKMAKER_REGISTRY, SUREBET_EXTRA_BOOKMAKERS

PERU_LEAGUE_KEYWORDS = ("liga 1", "liga 2", "liga 3", "liga femenina", "liga femenina peru", "copa peru", "copa perú", "primera division peru", "primera división peru", "segunda division peru", "segunda división peru", "liga peruana", "torneo peruano")
TARGET_PROFITS = (250, 500, 1000, 3000, 5000)

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
        guaranteed_return = min(int(stakes[key] * odds[key]) for key in stakes)
        guaranteed_profit = guaranteed_return - actual_total
        if guaranteed_profit >= target_profit:
            return {"stakes": stakes, "total_stake": actual_total, "total_return": guaranteed_return, "guaranteed_profit": guaranteed_profit, "roi_percent": (guaranteed_profit / actual_total) * 100, "implied_sum": implied_sum}
        total += 1


def calculate_stakes(outcomes: dict[str, dict[str, object]], total_stake: float) -> dict[str, object]:
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
    return {"stakes": stakes, "total_stake": actual_total, "total_return": guaranteed_return, "guaranteed_profit": profit, "roi_percent": (profit / actual_total) * 100, "implied_sum": implied_sum}


def build_target_profit_plans(outcomes: dict[str, dict[str, object]], targets: tuple[int, ...] = TARGET_PROFITS) -> dict[int, dict[str, object]]:
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
    text = str(market or "").lower().replace(" ", "_")
    for suffix in ("_ft", "_1h", "_2h", ":ft", ":1h", ":2h"):
        if text.endswith(suffix):
            return text[:-len(suffix)]
    aliases = {"moneyline": "1x2", "match_winner": "1x2", "win_draw_win": "1x2", "1x2": "1x2", "double_chance": "double_chance", "dc": "double_chance", "dnb": "dnb", "draw_no_bet": "dnb", "ah": "asian_handicap", "asian_handicap": "asian_handicap", "european_handicap": "european_handicap", "total": "total", "goals": "total", "over_under": "total", "btts": "btts", "both_teams_to_score": "btts", "team_total": "team_total", "corners": "corners", "cards": "cards", "spread": "asian_handicap", "handicap": "asian_handicap"}
    return aliases.get(text, text)


def _selection_key(selection: object) -> str:
    text = str(selection or "").strip().lower().replace(" ", "_")
    aliases = {"1": "home", "home_team": "home", "2": "away", "away_team": "away", "x": "draw", "tie": "draw"}
    text = text.split(":", 1)[-1].strip()
    return aliases.get(text, text)


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


def _as_line(value: object) -> float | None:
    try:
        return float(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _asian_return(line: float, side: str, result: str, odds: float) -> float:
    handicap = line if side == "home" else -line
    doubled = handicap * 2
    if abs(doubled - round(doubled)) > 1e-9:
        lower = math.floor(handicap * 2) / 2
        upper = math.ceil(handicap * 2) / 2
        return (_asian_return(lower if side == "home" else -lower, side, result, odds) + _asian_return(upper if side == "home" else -upper, side, result, odds)) / 2
    diff = {"home": 1.0, "draw": 0.0, "away": -1.0}[result]
    adjusted = diff + handicap
    if adjusted > 1e-9:
        return odds
    if abs(adjusted) <= 1e-9:
        return 1.0
    return 0.0


def _asian_vector(line: float | None, side: str, odds: float) -> tuple[float, float, float] | None:
    if line is None or side not in {"home", "away"}:
        return None
    return tuple(_asian_return(line, side, result, odds) for result in ("home", "draw", "away"))


def _settlement_vector(market: object, selection: object, line: object, odds: float) -> tuple[float, ...] | None:
    base = _market_base(market)
    key = _selection_key(selection)
    if base == "1x2":
        return {"home": (odds, 0.0, 0.0), "draw": (0.0, odds, 0.0), "away": (0.0, 0.0, odds)}.get(key)
    if base == "dnb":
        return {"home": (odds, 1.0, 0.0), "away": (0.0, 1.0, odds)}.get(key)
    if base == "double_chance":
        return {"1x": (odds, odds, 0.0), "12": (odds, 0.0, odds), "x2": (0.0, odds, odds)}.get(key)
    if base == "asian_handicap":
        return _asian_vector(_as_line(line), key, odds)
    if base == "btts":
        return {"yes": (odds, 0.0), "no": (0.0, odds)}.get(key)
    return None


def _solve_coverage(vectors: list[tuple[float, ...]]) -> tuple[float, list[float], list[float]] | None:
    if not vectors or len(vectors) > 4:
        return None
    states = len(vectors[0])
    n = len(vectors)
    if any(len(vector) != states for vector in vectors) or n != states:
        return None
    best = None
    for active in itertools.combinations(range(states), n):
        size = n + 1
        matrix = [[1.0] * n + [0.0]]
        rhs = [1.0]
        for state in active:
            matrix.append([vectors[i][state] for i in range(n)] + [-1.0])
            rhs.append(0.0)
        aug = [matrix[i] + [rhs[i]] for i in range(size)]
        valid = True
        for col in range(size):
            pivot = max(range(col, size), key=lambda row: abs(aug[row][col]))
            if abs(aug[pivot][col]) < 1e-10:
                valid = False
                break
            aug[col], aug[pivot] = aug[pivot], aug[col]
            divisor = aug[col][col]
            aug[col] = [value / divisor for value in aug[col]]
            for row in range(size):
                if row != col:
                    factor = aug[row][col]
                    if abs(factor) > 1e-12:
                        aug[row] = [aug[row][c] - factor * aug[col][c] for c in range(size + 1)]
        if not valid:
            continue
        solution = [aug[i][-1] for i in range(size)]
        stakes, guaranteed = solution[:n], solution[-1]
        if min(stakes) < -1e-8 or guaranteed <= 0:
            continue
        returns = [sum(stakes[i] * vectors[i][state] for i in range(n)) for state in range(states)]
        if min(returns) + 1e-8 < guaranteed:
            continue
        if best is None or guaranteed > best[0]:
            best = (guaranteed, stakes, returns)
    return best


def _coverage_stake_plan(quotes: list[dict[str, object]], total_stake: float | None = None) -> dict[str, object] | None:
    solved = _solve_coverage([quote["vector"] for quote in quotes])
    if solved is None or solved[0] <= 1.0 + 1e-9:
        return None
    guaranteed_ratio, ratios, _ = solved
    bankroll = float(total_stake) if total_stake else 100.0
    stakes = {str(i): round(bankroll * ratio, 2) for i, ratio in enumerate(ratios)}
    total = round(sum(stakes.values()), 2)
    guaranteed_return = round(total * guaranteed_ratio, 2)
    profit = round(guaranteed_return - total, 2)
    return {"stakes": stakes, "total_stake": total, "total_return": guaranteed_return, "guaranteed_profit": profit, "roi_percent": (profit / total) * 100, "implied_sum": 1.0 / guaranteed_ratio}


def _candidate_rows_for_match(rows: list[object]) -> list[object]:
    unique = {}
    for row in rows:
        if _market_base(row["market"]) not in {"1x2", "dnb", "double_chance", "asian_handicap", "btts"}:
            continue
        key = (str(row["bookmaker"]).lower(), _market_base(row["market"]), _selection_key(row["selection"]), row["line"])
        if key not in unique or float(row["odds"]) > float(unique[key]["odds"]):
            unique[key] = row
    return list(unique.values())


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
        row_time = _captured_at(row["captured_at"])
        current_time = _captured_at(current["captured_at"]) if current else None
        if current is None or (row_time is not None and (current_time is None or row_time > current_time)):
            latest[key] = row

    by_match = defaultdict(list)
    for row in latest.values():
        by_match[row["match_id"]].append(row)

    result: list[Arbitrage] = []
    seen = set()
    for current_match_id, match_rows in by_match.items():
        prepared = []
        for row in _candidate_rows_for_match(match_rows):
            vector = _settlement_vector(row["market"], row["selection"], row["line"], float(row["odds"]))
            if vector is not None:
                prepared.append({"row": row, "vector": vector})
        for size in (2, 3, 4):
            for combo in itertools.combinations(prepared, size):
                rows_combo = [item["row"] for item in combo]
                vectors = [item["vector"] for item in combo]
                if len({len(v) for v in vectors}) != 1 or len(vectors[0]) != size:
                    continue
                bookmakers = [str(row["bookmaker"]) for row in rows_combo]
                if len({name.lower() for name in bookmakers}) < 2:
                    continue
                classes = {classify_bookmaker(name) for name in bookmakers}
                if "UNKNOWN" in classes:
                    continue
                if normalized_scope == "peru" and classes != {"PERU"}:
                    continue
                if normalized_scope == "world" and classes not in ({"PERU", "INTERNATIONAL"}, {"INTERNATIONAL"}):
                    continue
                plan = _coverage_stake_plan([{"vector": vector} for vector in vectors], total_stake)
                if not plan:
                    continue
                identity = (current_match_id, tuple(sorted((str(row["bookmaker"]).lower(), _market_base(row["market"]), _selection_key(row["selection"]), row["line"], round(float(row["odds"]), 3)) for row in rows_combo)))
                if identity in seen:
                    continue
                seen.add(identity)
                competition = rows_combo[0]["competition"] or ""
                outcomes = {str(i): {"selection": _selection_key(row["selection"]), "market": _market_base(row["market"]), "line": row["line"], "bookmaker": row["bookmaker"], "odds": float(row["odds"]), "classification": classify_bookmaker(row["bookmaker"])} for i, row in enumerate(rows_combo)}
                same_market = len({_market_base(row["market"]) for row in rows_combo}) == 1
                market_label = rows_combo[0]["market"] if same_market else " + ".join(sorted({_market_base(row["market"]) for row in rows_combo}))
                result.append(Arbitrage(
                    match_id=current_match_id,
                    match=f"{rows_combo[0]['home_team']} vs {rows_combo[0]['away_team']}",
                    market=market_label,
                    line=rows_combo[0]["line"] if len({row["line"] for row in rows_combo}) == 1 else None,
                    outcomes=outcomes,
                    implied_sum=float(plan["implied_sum"]),
                    profit_margin=float(plan["roi_percent"]) / 100.0,
                    mode="live" if live else "pre_match",
                    competition=competition,
                    scope="peru" if normalized_scope == "peru" else _scope_for_competition(competition),
                    bookmaker_mix=" + ".join(sorted(classes)),
                    total_stake=int(round(float(plan["total_stake"]))) if total_stake else None,
                    total_return=int(round(float(plan["total_return"]))) if total_stake else None,
                    guaranteed_profit=int(round(float(plan["guaranteed_profit"]))) if total_stake else None,
                    roi_percent=float(plan["roi_percent"]) if total_stake else None,
                    target_profits=None,
                ))
                if len(result) >= limit:
                    break
            if len(result) >= limit:
                break
        if len(result) >= limit:
            break
    result.sort(key=lambda item: item.profit_margin, reverse=True)
    return result[:limit]
