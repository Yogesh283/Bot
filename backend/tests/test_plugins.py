from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from strategy_engine.strategies import get_strategy
from strategy_engine.strategies.base import Candle
from strategy_engine.targets import atr_targets, average_true_range, fixed_rr, stop_block_reason, trailed_stop


def _candle(close: float, *, high: float | None = None, low: float | None = None, when: datetime | None = None) -> Candle:
    moment = when or datetime.now(timezone.utc)
    return Candle(moment, close, close if high is None else high, close if low is None else low, close)


def test_ma_cross_plugin_keeps_the_completed_candle_rule():
    now = datetime.now(timezone.utc)
    candles = [_candle(1, when=now), _candle(1, when=now), _candle(1, when=now), _candle(5, when=now)]
    strategy = get_strategy("ma_cross", fast_period=2, slow_period=3, timeframe="M15")
    assert strategy.detect(candles).side == "BUY"
    flat = [_candle(1, when=now) for _ in range(4)]
    assert strategy.detect(flat) is None
    old = now - timedelta(hours=2)
    stale = [_candle(1, when=old) for _ in range(3)] + [_candle(5, when=old)]
    assert strategy.detect(stale) is None


def test_candle_break_needs_a_completed_breakout():
    now = datetime(2026, 10, 29, 8, 0, tzinfo=timezone.utc)
    strategy = get_strategy("candle_break")
    inside = [Candle(now, 10, 12, 9, 11), Candle(now, 11, 11.5, 10, 11)]
    assert strategy.detect(inside) is None
    broken = [Candle(now, 10, 12, 9, 11), Candle(now, 12, 13, 12, 12.5)]
    assert strategy.detect(broken).side == "BUY"
    assert strategy.detect([Candle(now, 10, 12, 9, 11)]) is None


def test_take_profit_math_and_breakeven():
    sl, tp = fixed_rr(side="BUY", entry=Decimal("2300.10"), sl_points=300, point=Decimal("0.01"), rr=Decimal("2"))
    assert sl == Decimal("2297.10")
    assert tp == Decimal("2306.10")
    candles = [{"high": 11, "low": 9, "close": 10}]
    for index in range(15):
        candles.append({"high": 12 + index, "low": 10 + index, "close": 11 + index})
    value = average_true_range(candles)
    assert value is not None
    atr_sl, atr_tp = atr_targets(side="SELL", entry=Decimal("100"), atr_value=value, sl_multiple=Decimal("1"), rr=Decimal("2"))
    assert atr_sl > Decimal("100")
    assert atr_tp < Decimal("100")
    assert stop_block_reason(entry=Decimal("100"), sl=Decimal("99.9"), tp=Decimal("100.2"), point=Decimal("0.01"), stops_level=50)
    assert trailed_stop(side="BUY", entry=Decimal("100"), price=Decimal("103"), current_sl=Decimal("97"), r_distance=Decimal("3")) == Decimal("100")
    assert trailed_stop(side="BUY", entry=Decimal("100"), price=Decimal("101"), current_sl=Decimal("97"), r_distance=Decimal("3")) is None
