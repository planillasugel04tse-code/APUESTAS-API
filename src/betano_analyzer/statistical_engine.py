from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, factorial
from typing import Any, Iterable


@dataclass(frozen=True)
class TeamMatch:
    goals_for: int
    goals_against: int
    home: bool = True


@dataclass(frozen=True)
class StatisticalReport:
    sample_size: int
    avg_goals_for: float
    avg_goals_against: float
    win_rate: float
    draw_rate: float
    loss_rate: float
    over_15_probability: float
    over_25_probability: float
    btts_probability: float
    clean_sheet_rate: float
    data_completeness: float
    status: str


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _poisson_pmf(lam: float, goals: int) -> float:
    if lam < 0 or goals < 0:
        return 0.0
    return exp(-lam) * (lam**goals) / factorial(goals)


def _total_probability(home_lambda: float, away_lambda: float, predicate) -> float:
    return sum(
        _poisson_pmf(home_lambda, h) * _poisson_pmf(away_lambda, a)
        for h in range(0, 11)
        for a in range(0, 11)
        if predicate(h, a)
    )


def build_report(matches: Iterable[TeamMatch], *, min_sample: int = 5) -> StatisticalReport:
    rows = list(matches)
    n = len(rows)
    if not rows:
        return StatisticalReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "DATOS_INSUFICIENTES")

    gf = _mean(row.goals_for for row in rows)
    ga = _mean(row.goals_against for row in rows)
    win = sum(row.goals_for > row.goals_against for row in rows) / n
    draw = sum(row.goals_for == row.goals_against for row in rows) / n
    loss = sum(row.goals_for < row.goals_against for row in rows) / n
    clean = sum(row.goals_against == 0 for row in rows) / n

    # The Poisson model is deliberately based only on the supplied observations.
    over15 = _total_probability(gf, ga, lambda h, a: h + a >= 2)
    over25 = _total_probability(gf, ga, lambda h, a: h + a >= 3)
    btts = _total_probability(gf, ga, lambda h, a: h >= 1 and a >= 1)
    completeness = min(1.0, n / max(min_sample, 1))

    return StatisticalReport(
        sample_size=n,
        avg_goals_for=round(gf, 4),
        avg_goals_against=round(ga, 4),
        win_rate=round(win, 4),
        draw_rate=round(draw, 4),
        loss_rate=round(loss, 4),
        over_15_probability=round(over15, 4),
        over_25_probability=round(over25, 4),
        btts_probability=round(btts, 4),
        clean_sheet_rate=round(clean, 4),
        data_completeness=round(completeness, 4),
        status="OK" if n >= min_sample else "DATOS_INSUFICIENTES",
    )


def _normalize_market(market: str) -> str:
    return " ".join(market.strip().lower().replace("_", " ").split())


def probability_for_selection(report: StatisticalReport, market: str, selection: str) -> float | None:
    market = _normalize_market(market)
    selection = _normalize_market(selection)
    if report.status != "OK":
        return None
    if market in {"goals", "total goals", "totals", "over/under"}:
        if "over 1.5" in selection or "más de 1.5" in selection or "mas de 1.5" in selection:
            return report.over_15_probability
        if "over 2.5" in selection or "más de 2.5" in selection or "mas de 2.5" in selection:
            return report.over_25_probability
    if market in {"btts", "ambos marcan"}:
        if selection in {"yes", "si", "sí", "ambos marcan"}:
            return report.btts_probability
        if selection in {"no", "ambos no marcan"}:
            return 1.0 - report.btts_probability
    if market in {"1x2", "resultado", "winner", "match winner"}:
        if selection in {"home", "local", "1", "gana local"}:
            return report.win_rate
        if selection in {"draw", "empate", "x"}:
            return report.draw_rate
        if selection in {"away", "visitante", "2", "gana visitante"}:
            return report.loss_rate
        if selection in {"1x", "local o empate"}:
            return report.win_rate + report.draw_rate
        if selection in {"x2", "empate o visitante"}:
            return report.draw_rate + report.loss_rate
    return None


def serialize_report(report: StatisticalReport) -> dict[str, Any]:
    return asdict(report)
