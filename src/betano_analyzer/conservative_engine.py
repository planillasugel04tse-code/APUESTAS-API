from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ConservativePick:
    original_market: str
    original_selection: str
    conservative_market: str
    conservative_selection: str
    rule: str


def _line_text(value: float) -> str:
    return f"{value:g}"


def transform(market: str, selection: str) -> ConservativePick:
    """Create a deterministic, lower-intensity football alternative.

    Only transforms markets where a common safer line is unambiguous. Unsupported
    markets are returned unchanged so the system never invents a different bet.
    """
    m = market.strip().lower()
    s = selection.strip()
    sl = s.lower()

    if m in {"1x2", "match winner", "ganador", "moneyline", "ml"}:
        if sl in {"1", "home", "local", "home win", "local gana"}:
            return ConservativePick(market, s, "double_chance", "1X", "ganador local -> 1X")
        if sl in {"2", "away", "visitante", "away win", "visitante gana"}:
            return ConservativePick(market, s, "double_chance", "X2", "ganador visitante -> X2")

    if m in {"goals", "total goals", "over/under", "goles", "totals"}:
        match = re.search(r"(?:over|más de)\s*(\d+(?:\.5|\.0)?)", sl)
        if match:
            line = float(match.group(1))
            new_line = line - 0.5
            if new_line >= 0:
                return ConservativePick(market, s, "goals", f"Over {_line_text(new_line)}", "bajar línea de goles 0.5")
        match = re.search(r"(?:under|menos de)\s*(\d+(?:\.5|\.0)?)", sl)
        if match:
            line = float(match.group(1))
            new_line = line + 0.5
            return ConservativePick(market, s, "goals", f"Under {_line_text(new_line)}", "subir línea de goles 0.5")

    if m in {"corners", "total corners", "corners total", "córners", "corner"}:
        match = re.search(r"(?:over|más de)\s*(\d+(?:\.5|\.0)?)", sl)
        if match:
            line = float(match.group(1))
            new_line = max(0, line - (2 if line >= 8 else 1))
            return ConservativePick(market, s, "corners", f"Over {_line_text(new_line)}", "bajar línea de córners 1-2")
        match = re.search(r"(?:under|menos de)\s*(\d+(?:\.5|\.0)?)", sl)
        if match:
            line = float(match.group(1))
            new_line = line + (2 if line >= 8 else 1)
            return ConservativePick(market, s, "corners", f"Under {_line_text(new_line)}", "subir línea de córners 1-2")

    if m in {"cards", "total cards", "cards total", "tarjetas", "card"}:
        match = re.search(r"(?:over|más de)\s*(\d+(?:\.5|\.0)?)", sl)
        if match:
            line = float(match.group(1))
            new_line = max(0, line - 1)
            return ConservativePick(market, s, "cards", f"Over {_line_text(new_line)}", "bajar línea de tarjetas 1")
        match = re.search(r"(?:under|menos de)\s*(\d+(?:\.5|\.0)?)", sl)
        if match:
            line = float(match.group(1))
            return ConservativePick(market, s, "cards", f"Under {_line_text(line + 1)}", "subir línea de tarjetas 1")

    if m in {"handicap", "asian handicap", "ah", "spread"}:
        match = re.search(r"^(home|local|1)\s*([+-]?\d+(?:\.5|\.0)?)$", sl)
        if match:
            line = float(match.group(2))
            if line < 0:
                new_line = line + 0.5
                return ConservativePick(market, s, "handicap", f"home {_line_text(new_line)}", "reducir hándicap local 0.5")
        match = re.search(r"^(away|visitante|2)\s*([+-]?\d+(?:\.5|\.0)?)$", sl)
        if match:
            line = float(match.group(2))
            if line < 0:
                new_line = line + 0.5
                return ConservativePick(market, s, "handicap", f"away {_line_text(new_line)}", "reducir hándicap visitante 0.5")

    return ConservativePick(market, s, market, s, "sin transformación automática")
