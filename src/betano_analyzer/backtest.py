from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class BacktestRow:
    result: str
    odds: float
    stake: float = 1.0


def evaluate(rows: Iterable[BacktestRow]) -> dict:
    rows = list(rows)
    settled = [r for r in rows if r.result in {"won", "lost", "push"} and r.odds > 1 and r.stake > 0]
    if not settled:
        return {"bets": 0, "wins": 0, "losses": 0, "pushes": 0, "stake": 0.0, "returns": 0.0, "net": 0.0, "roi": 0.0, "hit_rate": 0.0}
    wins = sum(r.result == "won" for r in settled)
    losses = sum(r.result == "lost" for r in settled)
    pushes = sum(r.result == "push" for r in settled)
    stake = sum(r.stake for r in settled)
    returns = sum(r.stake * r.odds if r.result == "won" else r.stake if r.result == "push" else 0.0 for r in settled)
    net = returns - stake
    return {"bets": len(settled), "wins": wins, "losses": losses, "pushes": pushes,
            "stake": stake, "returns": returns, "net": net,
            "roi": net / stake if stake else 0.0,
            "hit_rate": wins / len(settled) if settled else 0.0}


def compare_strategies(original: Iterable[BacktestRow], conservative: Iterable[BacktestRow]) -> dict:
    return {"original": evaluate(original), "conservative": evaluate(conservative)}
