from __future__ import annotations

from strategy_engine.strategies.base import Candle, Signal, Strategy
from strategy_engine.strategies.candle_break import CandleBreak
from strategy_engine.strategies.ma_cross import MaCross

REGISTRY: dict[str, type] = {
    "ma_cross": MaCross,
    "candle_break": CandleBreak,
}


def get_strategy(name: str, **options: object) -> Strategy:
    kind = REGISTRY.get(name)
    if kind is None:
        raise KeyError(f"Unknown strategy {name}.")
    return kind(**options)


__all__ = ["Candle", "Signal", "Strategy", "REGISTRY", "get_strategy"]
