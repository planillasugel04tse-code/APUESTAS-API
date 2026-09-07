from __future__ import annotations

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


def period_range(period: Period, reference: date | None = None) -> tuple[date | None, date | None]:
    day = reference or date.today()
    if period == Period.HOY:
        return day, day
    if period == Period.TODOS:
        return None, None

    if period == Period.LUNES_VIERNES:
        monday = day - timedelta(days=day.weekday())
        return monday, monday + timedelta(days=4)
    if period == Period.SABADO_DOMINGO:
        monday = day - timedelta(days=day.weekday())
        return monday + timedelta(days=5), monday + timedelta(days=6)

    # Ventanas móviles hasta hoy: el pasado sirve para medir estabilidad,
    # pero el radar siempre termina en la fecha actual.
    if period == Period.MES:
        return day - timedelta(days=30), day
    if period == Period.TRES_MESES:
        return day - timedelta(days=90), day
    if period == Period.SEIS_MESES:
        return day - timedelta(days=180), day
    raise ValueError(f"Periodo no soportado: {period}")
