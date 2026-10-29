from __future__ import annotations

from decimal import Decimal


def fixed_rr(*, side: str, entry: Decimal, sl_points: int, point: Decimal, rr: Decimal) -> tuple[Decimal, Decimal]:
    """Take profit is rr times the stop distance from the entry."""
    distance = Decimal(sl_points) * point
    if side == "BUY":
        return entry - distance, entry + (rr * distance)
    return entry + distance, entry - (rr * distance)


def average_true_range(candles: list[dict], period: int = 14) -> Decimal | None:
    if period < 1 or len(candles) < period + 1:
        return None
    ranges: list[Decimal] = []
    for index in range(1, len(candles)):
        high = Decimal(str(candles[index]["high"]))
        low = Decimal(str(candles[index]["low"]))
        previous_close = Decimal(str(candles[index - 1]["close"]))
        true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
        ranges.append(true_range)
    window = ranges[-period:]
    return sum(window, Decimal("0")) / Decimal(period)


def atr_targets(
    *,
    side: str,
    entry: Decimal,
    atr_value: Decimal,
    sl_multiple: Decimal,
    rr: Decimal,
) -> tuple[Decimal, Decimal]:
    distance = atr_value * sl_multiple
    if side == "BUY":
        return entry - distance, entry + (rr * distance)
    return entry + distance, entry - (rr * distance)


def stop_block_reason(*, entry: Decimal, sl: Decimal, tp: Decimal, point: Decimal, stops_level: int) -> str | None:
    if point <= 0:
        return "The symbol point size is unavailable, so stop loss could not be checked."
    sl_points = abs(entry - sl) / point
    tp_points = abs(entry - tp) / point
    if sl_points < Decimal(stops_level) or tp_points < Decimal(stops_level):
        return "Stop loss or take profit is closer than the broker stop distance."
    return None


def trailed_stop(*, side: str, entry: Decimal, price: Decimal, current_sl: Decimal, r_distance: Decimal) -> Decimal | None:
    """After price reaches 1R, move the stop to the entry. Returns None when the stop stays put."""
    if r_distance <= 0:
        return None
    if side == "BUY" and price >= entry + r_distance and current_sl < entry:
        return entry
    if side == "SELL" and price <= entry - r_distance and current_sl > entry:
        return entry
    return None
