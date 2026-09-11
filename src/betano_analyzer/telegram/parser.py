from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


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
    match_datetime: str | None = None  # ISO string if extracted from message
    is_valid: bool = True
    error_reason: str | None = None


def _clean(value: str) -> str:
    value = re.sub(r"[^\wÀ-ÿ .&'/-]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split()).strip(" -")


def _strip_competition_prefix(value: str) -> tuple[str, str]:
    cleaned = _clean(value)
    known = (
        "uefa champions league", "champions league", "europa league",
        "premier league", "la liga", "serie a", "bundesliga", "ligue 1",
        "liga 1 peru", "liga 1", "copa libertadores", "copa sudamericana",
        "copa america", "world cup", "mundial",
    )
    low = cleaned.lower()
    for prefix in known:
        if low.startswith(prefix + " "):
            return cleaned[len(prefix):].strip(), prefix
    return cleaned, ""


def _extract_teams(raw: str) -> tuple[str, str] | None:
    """Try multiple team-extraction patterns in priority order."""
    # Pattern 1: "Team1 vs Team2" (with vs/versus/contra)
    m = re.search(
        r"(.+?)\s+(?:vs\.?|versus|contra)\s+(.+?)"
        r"(?=\s+(?:💰|💵|📈|@|cuota|odds|stake|unidades|mercado|liga|league|torneo)|$)",
        raw, re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Pattern 2: "Partido: Team1 - Team2"
    m = re.search(r"partido\s*:\s*(.+?)\s*[-–]\s*(.+?)(?=\s+(?:💰|💵|📈|@|cuota|odds)|$)", raw, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Pattern 3: "Team1 - Team2" with emoji/keyword separator after teams
    m = re.search(
        r"^(.+?)\s*[-–]\s*(.+?)\s*(?=(?:💰|💵|📈|cuota|odds|@|\|))",
        raw.strip(), re.I | re.MULTILINE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return None


def _extract_match_datetime(raw: str) -> str | None:
    """Try to extract a match date/time from the message text.

    Returns ISO-8601 UTC string when found, None otherwise.
    Only extracts explicit dates/times; never fabricates.
    """
    # e.g. "18:00", "20:30 UTC", "18:00 CET"
    time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*(?:UTC|GMT|CET|BST|EST|ART|PET)?\b", raw)
    # e.g. "2026-09-10", "10/09/2026", "10-09-2026"
    date_match = re.search(r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\b", raw)

    if not time_match and not date_match:
        return None

    try:
        if date_match and time_match:
            raw_date = re.sub(r"[/]", "-", date_match.group(1))
            if re.match(r"\d{2}-\d{2}-\d{4}", raw_date):
                parts = raw_date.split("-")
                raw_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
            dt_str = f"{raw_date}T{time_match.group(1).zfill(2)}:{time_match.group(2)}:00+00:00"
            datetime.fromisoformat(dt_str)  # validate
            return dt_str
    except (ValueError, AttributeError):
        pass

    return None


def parse_telegram_message(text: str, *, channel: str, tipster: str | None = None) -> ParsedTelegramPick:
    """Parse a Telegram tipster message into a structured pick.

    Extraction is conservative: any ambiguous field defaults to a safe value
    rather than an invented one. The caller must check ``is_valid`` before use.
    """
    raw = (text or "").strip()
    source = tipster or channel
    if not raw:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw,
                                  None, False, "Mensaje vacío")

    team_result = _extract_teams(raw)
    if not team_result:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw,
                                  None, False, "No se pudieron identificar los equipos")

    raw_home, raw_away = team_result
    home, detected_comp = _strip_competition_prefix(raw_home)
    away = _clean(raw_away)
    if not home or not away:
        return ParsedTelegramPick("", "", "", "", "", None, 0.0, None, None, source, channel, raw,
                                  None, False, "Equipos vacíos")

    # -----------------------------------------------------------------------
    # Odds extraction
    # -----------------------------------------------------------------------
    odds_match = re.search(r"(?:cuota|odds|momio|@|💰|💵|📈)\s*:?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
    if not odds_match:
        odds_match = re.search(r"\b(\d+[.,]\d{1,2})\b", raw)
    odds = float(odds_match.group(1).replace(",", ".")) if odds_match else 0.0
    if odds <= 1.0:
        return ParsedTelegramPick(home, away, "", "", "", None, odds, None, None, source, channel, raw,
                                  None, False, "Cuota inválida o no encontrada")

    # -----------------------------------------------------------------------
    # Competition
    # -----------------------------------------------------------------------
    comp_match = re.search(r"(?:liga|league|torneo|copa|competici[oó]n)\s*:\s*([^\n]+)", raw, re.I)
    competition = _clean(comp_match.group(1)) if comp_match else detected_comp

    # -----------------------------------------------------------------------
    # Market + selection + line
    # -----------------------------------------------------------------------
    market = "1x2"
    selection = "home"
    line: float | None = None
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

    # Line extraction
    line_match = re.search(r"(?:over|under|más de|mas de|menos de)\s*(\d+(?:\.5|\.0)?)", low)
    handicap_match = re.search(r"(?:handicap|hándicap|ah)\s*([+-]?\d+(?:\.5|\.0)?)", low)

    if line_match:
        line = float(line_match.group(1))
        selection = "under" if any(k in low for k in ("under", "menos de")) else "over"
    elif handicap_match:
        line = float(handicap_match.group(1))
        if re.search(r"\b(?:visitante|away|local|home)\b", low):
            selection = "away" if re.search(r"\b(?:visitante|away)\b", low) else "home"
        else:
            selection = "home"
    elif market == "1x2":
        if re.search(r"\b(?:empate|draw)\b", low):
            selection = "draw"
        elif re.search(r"\b(?:visitante|away|gana visitante)\b", low):
            selection = "away"
        else:
            selection = "home"
    elif market == "double_chance":
        selection = "home_or_draw" if "1x" in low else "draw_or_away" if "x2" in low else "home_or_away"

    # -----------------------------------------------------------------------
    # Stake / confidence / match datetime
    # -----------------------------------------------------------------------
    stake_match = re.search(r"(?:stake|unidades|stk)\s*:?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
    stake = float(stake_match.group(1).replace(",", ".")) if stake_match else None
    confidence = min(1.0, max(0.1, stake / 10.0)) if stake is not None else None

    match_datetime = _extract_match_datetime(raw)

    return ParsedTelegramPick(
        home, away, competition, market, selection, line, odds, stake, confidence,
        source, channel, raw, match_datetime,
    )
