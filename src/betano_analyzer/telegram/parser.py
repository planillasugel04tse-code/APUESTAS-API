from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedTelegramPick:
    home_team: str
    away_team: str
    competition: str
    market: str
    selection: str
    line: float | None
    odds: float
    stake: float | None
    confidence: float | None
    tipster: str
    channel: str
    raw_text: str
    is_valid: bool = True
    error_reason: str | None = None


def _clean(value: str) -> str:
    value = re.sub(r"[^\wÀ-ÿ .&'/-]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split()).strip(" -")


def parse_telegram_message(text: str, *, channel: str, tipster: str | None = None) -> ParsedTelegramPick:
    raw = (text or "").strip()
    source = tipster or channel
    if not raw:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw, False, "Mensaje vacío")

    match = re.search(r"(.+?)\s+(?:vs\.?|versus|contra)\s+(.+?)(?=\s+(?:💰|💵|📈|@|cuota|odds|stake|unidades)\b|$)", raw, re.I)
    if not match:
        match = re.search(r"partido\s*:\s*(.+?)\s*[-–]\s*(.+?)(?=\s+(?:💰|💵|📈|@|cuota|odds)\b|$)", raw, re.I)
    if not match:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw, False, "No se pudieron identificar los equipos")

    home, away = _clean(match.group(1)), _clean(match.group(2))
    if not home or not away:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw, False, "Equipos vacíos")

    odds_match = re.search(r"(?:cuota|odds|momio|@|💰|💵|📈)\s*:?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
    if not odds_match:
        odds_match = re.search(r"\b(\d+[.,]\d{1,2})\b", raw)
    odds = float(odds_match.group(1).replace(",", ".")) if odds_match else 0.0
    if odds <= 1.0:
        return ParsedTelegramPick(home, away, "", "", "", None, odds, None, None, source, channel, raw, False, "Cuota inválida o no encontrada")

    comp_match = re.search(r"(?:liga|league|torneo|copa|competici[oó]n)\s*:\s*([^\n]+)", raw, re.I)
    competition = _clean(comp_match.group(1)) if comp_match else ""

    market = "1x2"
    selection = "home"
    line: float | None = None
    low = raw.lower()
    if "ambos" in low or "btts" in low:
        market, selection = "btts", ("no" if re.search(r"\b(?:no|falso)\b", low) else "yes")
    elif any(k in low for k in ("corner", "córner", "corners")):
        market = "corners"
    elif any(k in low for k in ("tarjeta", "tarjetas", "cards", "card")):
        market = "cards"
    elif any(k in low for k in ("over", "under", "goles", "más de", "mas de", "menos de")):
        market = "goals"
    elif any(k in low for k in ("1x", "x2", "12", "doble oportunidad", "doble opcion")):
        market = "double_chance"

    line_match = re.search(r"(?:over|under|más de|mas de|menos de)\s*(\d+(?:\.5|\.0)?)", low)
    if line_match:
        line = float(line_match.group(1))
        selection = ("under" if any(k in low for k in ("under", "menos de")) else "over")
    elif market == "1x2":
        if re.search(r"\b(?:empate|draw)\b", low):
            selection = "draw"
        elif re.search(r"\b(?:visitante|away|gana visitante)\b", low):
            selection = "away"
        else:
            selection = "home"
    elif market == "double_chance":
        selection = "home_or_draw" if "1x" in low else "draw_or_away" if "x2" in low else "home_or_away"

    stake_match = re.search(r"(?:stake|unidades|stk)\s*:?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
    stake = float(stake_match.group(1).replace(",", ".")) if stake_match else None
    confidence = min(1.0, max(0.1, stake / 10.0)) if stake is not None else None

    return ParsedTelegramPick(home, away, competition, market, selection, line, odds, stake, confidence, source, channel, raw)
