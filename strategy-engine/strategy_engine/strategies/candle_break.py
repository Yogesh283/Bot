from __future__ import annotations

from strategy_engine.strategies.base import Candle, Signal


class CandleBreak:
    """Example pattern: the latest completed close breaks the previous completed candle."""

    name = "candle_break"

    def detect(self, candles: list[Candle]) -> Signal | None:
        if len(candles) < 2:
            return None
        previous, latest = candles[-2], candles[-1]
        if latest.close > previous.high:
            return Signal("BUY", latest.time)
        if latest.close < previous.low:
            return Signal("SELL", latest.time)
        return None
