from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from enum import Enum


class Period(str, Enum):
    HOY = "hoy"
    LUNES_VIERNES = "lunes-viernes"
    SABADO_DOMINGO = "sabado-domingo"
    MES = "mes"
    TRES_MESES = "3-meses"
    SEIS_MESES = "6-meses"
    TODOS = "todos"


def shift_month(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def period_range(period: Period, reference: date | None = None) -> tuple[date | None, date | None]:
    day = reference or date.today()
    if period == Period.HOY:
        return day, day
    if period == Period.TODOS:
        return None, None

    monday = day - timedelta(days=day.weekday())
    if period == Period.LUNES_VIERNES:
        return monday, monday + timedelta(days=4)
    if period == Period.SABADO_DOMINGO:
        return monday + timedelta(days=5), monday + timedelta(days=6)
    if period == Period.MES:
        start = day.replace(day=1)
        return start, shift_month(start, 1) - timedelta(days=1)
    if period == Period.TRES_MESES:
        start = shift_month(day.replace(day=1), -2)
        return start, shift_month(day.replace(day=1), 1) - timedelta(days=1)
    if period == Period.SEIS_MESES:
        start = shift_month(day.replace(day=1), -5)
        return start, shift_month(day.replace(day=1), 1) - timedelta(days=1)
    raise ValueError(f"Periodo no soportado: {period}")
