from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial
from typing import Iterable


SUPPORTED_MARKETS = {"goals", "corners"}


@dataclass(frozen=True)
class RangeGap:
    market: str
    lower_line: float
    upper_line: float
    gap: float
    probability_between: float
    risk_score: float
    interpretation: str


def _poisson_pmf(k: int, lam: float) -> float:
    if k < 0 or lam < 0:
        return 0.0
    return exp(-lam) * (lam**k) / factorial(k)


def probability_between_lines(lower_line: float, upper_line: float, expected_total: float) -> float:
    """Probability of an integer total strictly inside a meaningful line gap.

    A one-unit half-line interval such as 2.5–3.5 is treated as having no
    usable integer gap. A wider interval (for example 8.5–10.5) can contain
    integer totals and is evaluated with a Poisson approximation.
    """
    if expected_total < 0 or upper_line <= lower_line or upper_line - lower_line <= 1.0:
        return 0.0
    first = int(lower_line) + 1
    last = int(upper_line - 1e-12)
    if last < first:
        return 0.0
    return min(1.0, sum(_poisson_pmf(k, expected_total) for k in range(first, last + 1)))


def analyze_range(
    market: str,
    lines: Iterable[float],
    expected_total: float,
    *,
    minimum_gap: float = 0.5,
) -> list[RangeGap]:
    """Find meaningful gaps between bookmaker lines for goals/corners.

    This is an analysis-only component: it does not place or recommend bets.
    A larger probability of the total landing inside a gap lowers the risk score.
    """
    normalized = str(market or "").strip().lower()
    if normalized not in SUPPORTED_MARKETS:
        raise ValueError("market must be goals or corners")
    if expected_total < 0:
        raise ValueError("expected_total must be non-negative")

    unique = sorted({float(line) for line in lines})
    result: list[RangeGap] = []
    for lower, upper in zip(unique, unique[1:]):
        gap = upper - lower
        if gap < minimum_gap:
            continue
        probability = probability_between_lines(lower, upper, expected_total)
        risk_score = round(100.0 * probability, 2)
        interpretation = "ALTO" if probability >= 0.35 else "MEDIO" if probability >= 0.15 else "BAJO"
        result.append(
            RangeGap(
                market=normalized,
                lower_line=lower,
                upper_line=upper,
                gap=gap,
                probability_between=round(probability, 6),
                risk_score=risk_score,
                interpretation=interpretation,
            )
        )
    return result
