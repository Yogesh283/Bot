from __future__ import annotations

from datetime import datetime, timezone

from strategy_engine.moving_average import MovingAverageConfig, analyze_closes
from strategy_engine.strategies.base import Candle, Signal


class MaCross:
    """Completed-candle moving-average cross. Entry rules stay in analyze_closes."""

    name = "ma_cross"

    def __init__(self, fast_period: int = 10, slow_period: int = 20, timeframe: str = "M15") -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.timeframe = timeframe

    def detect(self, candles: list[Candle]) -> Signal | None:
        if not candles:
            return None
        analysis = analyze_closes(
            [candle.close for candle in candles],
            candles[-1].time,
            MovingAverageConfig(self.fast_period, self.slow_period),
            timeframe=self.timeframe,
            now=datetime.now(timezone.utc),
        )
        if analysis.data_status != "ok" or analysis.signal not in {"BUY", "SELL"}:
            return None
        return Signal(analysis.signal, candles[-1].time)
