from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum


class Period(str, Enum):
    HOY = "hoy"
    LUNES_VIERNES = "lunes-viernes"
    SABADO_DOMINGO = "sabado-domingo"
    TODOS = "todos"


def period_range(period: Period, reference: date | None = None) -> tuple[date | None, date | None]:
    """Return the inclusive date range represented by a dashboard tab."""
    day = reference or date.today()
    if period == Period.HOY:
        return day, day
    if period == Period.TODOS:
        return None, None

    monday = day - timedelta(days=day.weekday())
    if period == Period.LUNES_VIERNES:
        return monday, monday + timedelta(days=4)

    # Weekend belonging to the same Monday-Sunday week.
    return monday + timedelta(days=5), monday + timedelta(days=6)
