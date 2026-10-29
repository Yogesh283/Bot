"""Registered strategy calculations. The website never executes arbitrary Python."""

from strategy_engine.alarm import raise_alarm
from strategy_engine.moving_average import MovingAverageConfig, analyze_closes
from strategy_engine.risk import MarketSnapshot, RiskLimits, assess_demo_order

__all__ = [
    "MovingAverageConfig",
    "analyze_closes",
    "raise_alarm",
    "MarketSnapshot",
    "RiskLimits",
    "assess_demo_order",
]
