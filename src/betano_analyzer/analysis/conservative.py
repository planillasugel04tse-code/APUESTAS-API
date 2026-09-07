from __future__ import annotations


def conservative_market(market: str, line: float | None = None) -> tuple[str, float | None]:
    """Return a safer candidate line without inventing an outcome.

    The transformation is deliberately limited to common football markets.
    """
    normalized = market.strip().lower()
    if normalized in {"1x", "x2"}:
        return normalized, line
    if normalized == "over" and line is not None:
        return "over", max(0.0, line - 0.5)
    if normalized == "corners_over" and line is not None:
        return "corners_over", max(0.0, line - 2.0)
    if normalized == "goals_over" and line is not None:
        return "goals_over", max(0.0, line - 0.5)
    return normalized, line
