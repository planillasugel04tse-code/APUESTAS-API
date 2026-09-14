from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


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
    match_datetime: str | None = None
    is_valid: bool = True
    error_reason: str | None = None


def _clean(value: str) -> str:
    value = re.sub(r"[^\wÀ-ÿ .&'/-]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split()).strip(" -")


def _strip_competition_prefix(value: str) -> tuple[str, str]:
    cleaned = _clean(value)
    known = ("uefa champions league", "champions league", "europa league", "premier league", "la liga", "serie a", "bundesliga", "ligue 1", "liga 1 peru", "liga 1", "copa libertadores", "copa sudamericana", "copa america", "world cup", "mundial")
    low = cleaned.lower()
    for prefix in known:
        if low.startswith(prefix + " "):
            return cleaned[len(prefix):].strip(), prefix
    return cleaned, ""


def _extract_teams(raw: str) -> tuple[str, str] | None:
    patterns = (
        r"(.+?)\s+(?:vs\.?|versus|contra)\s+(.+?)(?=\s+(?:💰|💵|📈|@|cuota|odds|stake|unidades|mercado|liga|league|torneo)|$)",
        r"partido\s*:\s*(.+?)\s*[-–]\s*(.+?)(?=\s+(?:💰|💵|📈|@|cuota|odds)|$)",
        r"^(.+?)\s*[-–]\s*(.+?)\s*(?=(?:💰|💵|📈|cuota|odds|@|\|))",
    )
    for pattern in patterns:
        match = re.search(pattern, raw.strip(), re.I | re.MULTILINE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


def _extract_match_datetime(raw: str) -> str | None:
    time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*(?:UTC|GMT|CET|BST|EST|ART|PET)?\b", raw)
    date_match = re.search(r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\b", raw)
    if not time_match or not date_match:
        return None
    try:
        raw_date = date_match.group(1).replace("/", "-")
        if re.match(r"\d{2}-\d{2}-\d{4}", raw_date):
            day, month, year = raw_date.split("-")
            raw_date = f"{year}-{month}-{day}"
        dt = datetime.fromisoformat(f"{raw_date}T{time_match.group(1).zfill(2)}:{time_match.group(2)}:00")
        return dt.isoformat() + "+00:00"
    except ValueError:
        return None


def parse_telegram_message(text: str, *, channel: str, tipster: str | None = None) -> ParsedTelegramPick:
    raw = (text or "").strip()
    source = tipster or channel
    if not raw:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw, None, False, "Mensaje vacío")
    team_result = _extract_teams(raw)
    if not team_result:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw, None, False, "No se pudieron identificar los equipos")
    raw_home, raw_away = team_result
    home, detected_comp = _strip_competition_prefix(raw_home)
    away = _clean(raw_away)
    if not home or not away:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw, None, False, "Equipos vacíos")

    odds_match = re.search(r"(?:cuota|odds|momio|@|💰|💵|📈)\s*:?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
    if not odds_match:
        odds_match = re.search(r"\b(\d+[.,]\d{1,2})\b", raw)
    odds = float(odds_match.group(1).replace(",", ".")) if odds_match else 0.0
    if odds <= 1.0:
        return ParsedTelegramPick(home, away, "", "", "", None, odds, None, None, source, channel, raw, None, False, "Cuota inválida o no encontrada")

    comp_match = re.search(r"(?:liga|league|torneo|copa|competici[oó]n)\s*:\s*([^\n|]+)", raw, re.I)
    competition = _clean(comp_match.group(1)) if comp_match else detected_comp

    market, selection, line = "1x2", "home", None
    low = raw.lower()
    if "ambos" in low or "btts" in low:
        market = "btts"
        selection = "no" if re.search(r"\b(?:no|falso)\b", low) else "yes"
    elif any(k in low for k in ("corner", "córner", "corners")):
        market = "corners"
    elif any(k in low for k in ("tarjeta", "tarjetas", "cards", "card")):
        market = "cards"
    elif re.search(r"\b(?:handicap|h[aá]ndicap|asian\s+handicap|\bah\b|spread)\b", low):
        market = "asian_handicap"
    elif any(k in low for k in ("over", "under", "goles", "más de", "mas de", "menos de")):
        market = "goals"
    elif any(k in low for k in ("1x", "x2", "12", "doble oportunidad", "doble opcion")):
        market = "double_chance"

    line_match = re.search(r"(?:over|under|más de|mas de|menos de)\s*(\d+(?:\.5|\.0)?)", low)
    handicap_match = re.search(r"(?:handicap|hándicap|ah)\s*([+-]?\d+(?:\.5|\.0)?)", low)
    if line_match:
        line = float(line_match.group(1))
        selection = "under" if re.search(r"(?:under|menos de)", low) else "over"
    elif handicap_match:
        line = float(handicap_match.group(1))
        selection = "away" if re.search(r"\b(?:visitante|away)\b", low) else "home"
    elif market == "1x2":
        if re.search(r"\b(?:empate|draw)\b", low):
            selection = "draw"
        elif re.search(r"\b(?:visitante|away|gana visitante)\b", low):
            selection = "away"
    elif market == "double_chance":
        selection = "home_or_draw" if "1x" in low else "draw_or_away" if "x2" in low else "home_or_away"

    stake_match = re.search(r"(?:stake|unidades|stk)\s*:?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
    stake = float(stake_match.group(1).replace(",", ".")) if stake_match else None
    confidence = min(1.0, max(0.1, stake / 10.0)) if stake is not None else None
    return ParsedTelegramPick(home, away, competition, market, selection, line, odds, stake, confidence, source, channel, raw, _extract_match_datetime(raw))
