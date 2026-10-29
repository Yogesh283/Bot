from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from strategy_engine.candles import candle_is_stale

SignalName = Literal["BUY", "SELL", "NO_SIGNAL"]


@dataclass(frozen=True)
class MovingAverageConfig:
    fast_period: int
    slow_period: int

    def problem(self) -> str | None:
        if self.fast_period < 2 or self.slow_period < 3:
            return "Fast and slow periods must be at least 2 and 3."
        if self.fast_period >= self.slow_period:
            return "The fast moving average must be shorter than the slow one."
        return None


@dataclass(frozen=True)
class Analysis:
    signal: SignalName
    fast_ma: float | None
    slow_ma: float | None
    candle_time: datetime | None
    data_status: Literal["ok", "missing", "stale", "invalid"]
    detail: str


def simple_moving_average(values: list[float], period: int) -> float | None:
    if period < 1 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def analyze_closes(
    closes: list[float],
    candle_time: datetime | None,
    config: MovingAverageConfig,
    *,
    timeframe: str,
    now: datetime | None = None,
) -> Analysis:
    """Crossover on completed closes only. The caller must already drop the forming bar."""
    problem = config.problem()
    if problem:
        return Analysis("NO_SIGNAL", None, None, candle_time, "invalid", problem)
    if candle_time is None or len(closes) < config.slow_period + 1:
        return Analysis(
            "NO_SIGNAL",
            None,
            None,
            candle_time,
            "missing",
            "Not enough completed candles to calculate both moving averages.",
        )
    if candle_is_stale(candle_time, timeframe, now):
        return Analysis(
            "NO_SIGNAL",
            None,
            None,
            candle_time,
            "stale",
            "The latest completed candle is too old. No signal was produced.",
        )
    previous_fast = simple_moving_average(closes[:-1], config.fast_period)
    previous_slow = simple_moving_average(closes[:-1], config.slow_period)
    fast_value = simple_moving_average(closes, config.fast_period)
    slow_value = simple_moving_average(closes, config.slow_period)
    if None in (previous_fast, previous_slow, fast_value, slow_value):
        return Analysis("NO_SIGNAL", fast_value, slow_value, candle_time, "missing", "Moving averages could not be calculated.")
    assert previous_fast is not None and previous_slow is not None
    assert fast_value is not None and slow_value is not None
    if previous_fast <= previous_slow and fast_value > slow_value:
        return Analysis("BUY", fast_value, slow_value, candle_time, "ok", "Fast average crossed above the slow average.")
    if previous_fast >= previous_slow and fast_value < slow_value:
        return Analysis("SELL", fast_value, slow_value, candle_time, "ok", "Fast average crossed below the slow average.")
    return Analysis("NO_SIGNAL", fast_value, slow_value, candle_time, "ok", "No completed crossover on the latest candle.")
