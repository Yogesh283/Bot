from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from strategy_engine.candles import drop_forming_bar
from strategy_engine.moving_average import MovingAverageConfig, analyze_closes, simple_moving_average
from strategy_engine.risk import MarketSnapshot, RiskLimits, assess_demo_order


def _limits(**overrides) -> RiskLimits:
    values = dict(
        lot_size=Decimal("0.01"),
        stop_loss_points=300,
        take_profit_points=600,
        max_open_positions=1,
        max_spread_points=50,
        max_daily_loss=Decimal("100"),
    )
    values.update(overrides)
    return RiskLimits(**values)


def _market(**overrides) -> MarketSnapshot:
    values = dict(
        environment="demo",
        free_margin=Decimal("1000"),
        margin_required=Decimal("50"),
        spread_points=Decimal("10"),
        min_volume=Decimal("0.01"),
        max_volume=Decimal("100"),
        volume_step=Decimal("0.01"),
        stops_level=20,
        symbol_trade_mode="full",
        open_positions=0,
        realized_loss_today=Decimal("0"),
        bid=Decimal("2300"),
        ask=Decimal("2300.10"),
        point=Decimal("0.01"),
    )
    values.update(overrides)
    return MarketSnapshot(**values)


def test_simple_moving_average_uses_the_latest_window():
    assert simple_moving_average([1, 2, 3, 4], 2) == 3.5
    assert simple_moving_average([1], 2) is None


def test_buy_and_sell_use_only_completed_closes():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    buy = analyze_closes([1, 1, 1, 5], now, MovingAverageConfig(2, 3), timeframe="M15", now=now)
    assert buy.signal == "BUY"
    assert buy.data_status == "ok"
    assert buy.fast_ma == 3
    sell = analyze_closes([5, 5, 5, 1], now, MovingAverageConfig(2, 3), timeframe="M15", now=now)
    assert sell.signal == "SELL"
    flat = analyze_closes([1, 1, 1, 1], now, MovingAverageConfig(2, 3), timeframe="M15", now=now)
    assert flat.signal == "NO_SIGNAL"
    assert flat.fast_ma == 1
    assert flat.slow_ma == 1


def test_missing_stale_and_invalid_market_data_produce_no_signal():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    missing = analyze_closes([1, 2], now, MovingAverageConfig(2, 3), timeframe="M15", now=now)
    assert missing.data_status == "missing"
    assert missing.signal == "NO_SIGNAL"
    stale = analyze_closes(
        [1, 1, 1, 5],
        now - timedelta(hours=2),
        MovingAverageConfig(2, 3),
        timeframe="M15",
        now=now,
    )
    assert stale.data_status == "stale"
    assert stale.signal == "NO_SIGNAL"
    invalid = analyze_closes([1, 1, 1, 5], now, MovingAverageConfig(5, 3), timeframe="M15", now=now)
    assert invalid.data_status == "invalid"


def test_forming_bar_is_dropped_before_analysis():
    bars = [{"close": 1}, {"close": 1}, {"close": 1}, {"close": 5}, {"close": 99}]
    completed = drop_forming_bar(bars)
    assert [bar["close"] for bar in completed] == [1, 1, 1, 5]
    assert drop_forming_bar([{"close": 1}]) == []


def test_risk_rejects_bad_volume_margin_stop_and_live_accounts():
    assert "volume step" in assess_demo_order(_limits(lot_size=Decimal("0.015")), _market(), "BUY")
    assert "Free margin" in assess_demo_order(_limits(), _market(free_margin=Decimal("1")), "BUY")
    assert "stop distance" in assess_demo_order(_limits(stop_loss_points=5), _market(stops_level=50), "BUY")
    assert "Contest" in assess_demo_order(_limits(), _market(environment="contest"), "BUY")
    assert assess_demo_order(_limits(), _market(environment="live"), "BUY") is None
    assert assess_demo_order(_limits(), _market(), "BUY") is None
