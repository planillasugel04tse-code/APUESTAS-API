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


def transform(market: str, selection: str) -> ConservativePick:
    m = market.strip().lower()
    s = selection.strip()

    if m in {"1x2", "match winner", "ganador", "moneyline"}:
        if s.lower() in {"1", "home", "local"}:
            return ConservativePick(market, s, "double_chance", "1X", "ganador local -> 1X")
        if s.lower() in {"2", "away", "visitante"}:
            return ConservativePick(market, s, "double_chance", "X2", "ganador visitante -> X2")

    if m in {"goals", "total goals", "over/under", "goles"}:
        match = re.search(r"over\s*(\d+(?:\.5)?)", s.lower())
        if match:
            line = float(match.group(1))
            new_line = line - 0.5
            if new_line >= 0:
                return ConservativePick(market, s, "goals", f"Over {new_line:g}", "bajar línea de goles 0.5")
        match = re.search(r"under\s*(\d+(?:\.5)?)", s.lower())
        if match:
            line = float(match.group(1))
            new_line = line + 0.5
            return ConservativePick(market, s, "goals", f"Under {new_line:g}", "subir línea de goles 0.5")

    if m in {"corners", "total corners", "corners total", "córners"}:
        match = re.search(r"(?:over|más de)\s*(\d+(?:\.5)?)", s.lower())
        if match:
            line = float(match.group(1))
            new_line = max(0, line - 2)
            return ConservativePick(market, s, "corners", f"Over {new_line:g}", "bajar línea de córners 2")

    return ConservativePick(market, s, market, s, "sin transformación automática")
