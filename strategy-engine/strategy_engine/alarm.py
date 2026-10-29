"""Look back over completed candles and allow a trade only in the confirmed direction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from strategy_engine.moving_average import MovingAverageConfig, analyze_closes

AlarmSide = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Alarm:
    side: AlarmSide | None
    fast_ma: float | None
    slow_ma: float | None
    detail: str


def raise_alarm(
    closes: list[float],
    candle_time: datetime | None,
    config: MovingAverageConfig,
    *,
    timeframe: str,
    now: datetime | None = None,
) -> Alarm:
    """Analyze past completed candles. No trade is created unless the cross and the close agree."""
    analysis = analyze_closes(closes, candle_time, config, timeframe=timeframe, now=now)
    if analysis.signal not in {"BUY", "SELL"} or analysis.data_status != "ok" or analysis.slow_ma is None or not closes:
        return Alarm(None, analysis.fast_ma, analysis.slow_ma, analysis.detail)
    last_close = closes[-1]
    if analysis.signal == "BUY" and last_close <= analysis.slow_ma:
        return Alarm(None, analysis.fast_ma, analysis.slow_ma, "The close is not above the slow average, so no trade was created.")
    if analysis.signal == "SELL" and last_close >= analysis.slow_ma:
        return Alarm(None, analysis.fast_ma, analysis.slow_ma, "The close is not below the slow average, so no trade was created.")
    return Alarm(analysis.signal, analysis.fast_ma, analysis.slow_ma, analysis.detail)
