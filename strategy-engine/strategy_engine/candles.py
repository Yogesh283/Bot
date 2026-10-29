from __future__ import annotations

from datetime import datetime, timedelta, timezone

TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


def drop_forming_bar(bars: list) -> list:
    """MT5 includes the current unfinished bar at the end. Signals use completed bars only."""
    if len(bars) < 2:
        return []
    return list(bars[:-1])


def candle_is_stale(candle_time: datetime, timeframe: str, now: datetime | None = None) -> bool:
    seconds = TIMEFRAME_SECONDS.get(timeframe)
    if seconds is None:
        return True
    current = now or datetime.now(timezone.utc)
    if candle_time.tzinfo is None:
        candle_time = candle_time.replace(tzinfo=timezone.utc)
    return current - candle_time > timedelta(seconds=seconds * 3)
