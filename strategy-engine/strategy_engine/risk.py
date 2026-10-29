from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskLimits:
    lot_size: Decimal
    stop_loss_points: int
    take_profit_points: int
    max_open_positions: int
    max_spread_points: int
    max_daily_loss: Decimal


@dataclass(frozen=True)
class MarketSnapshot:
    environment: str
    free_margin: Decimal | None
    margin_required: Decimal | None
    spread_points: Decimal | None
    min_volume: Decimal
    max_volume: Decimal
    volume_step: Decimal
    stops_level: int
    symbol_trade_mode: str
    open_positions: int
    realized_loss_today: Decimal | None
    bid: Decimal | None
    ask: Decimal | None
    point: Decimal | None


def _volume_matches_step(volume: Decimal, minimum: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return False
    steps = (volume - minimum) / step
    return steps == steps.to_integral_value()


def assess_demo_order(limits: RiskLimits, market: MarketSnapshot, side: str) -> str | None:
    """Return a rejection reason, or None when the Demo order is allowed."""
    if market.environment not in {"demo", "live"}:
        return "Contest accounts are rejected. Connect a Demo or Live account."
    if market.symbol_trade_mode != "full":
        return "This symbol is not fully enabled for trading at the broker."
    if limits.lot_size <= 0:
        return "Lot size must be greater than zero."
    if limits.lot_size < market.min_volume or limits.lot_size > market.max_volume:
        return "Lot size is outside the broker minimum or maximum volume."
    if not _volume_matches_step(limits.lot_size, market.min_volume, market.volume_step):
        return "Lot size does not match the broker volume step."
    if market.free_margin is None or market.margin_required is None:
        return "Free margin could not be checked, so no Demo order was created."
    if market.free_margin < market.margin_required:
        return "Free margin is not enough for this lot size."
    if market.spread_points is None:
        return "Spread is unavailable, so no Demo order was created."
    if market.spread_points > Decimal(limits.max_spread_points):
        return "The current spread is above the configured maximum."
    if market.open_positions >= limits.max_open_positions:
        return "The maximum number of open positions is already reached."
    if market.realized_loss_today is None:
        return "Today's loss is unknown, so no Demo order was created."
    if market.realized_loss_today >= limits.max_daily_loss:
        return "The maximum daily loss has been reached."
    if limits.stop_loss_points <= 0 or limits.take_profit_points <= 0:
        return "Stop loss and take profit are required."
    if limits.stop_loss_points < market.stops_level or limits.take_profit_points < market.stops_level:
        return "Stop loss or take profit is closer than the broker stop distance."
    if market.point is None or market.point <= 0:
        return "The symbol point size is unavailable, so stop loss could not be checked."
    entry = market.ask if side == "BUY" else market.bid
    if entry is None or entry <= 0:
        return "There is no valid price for this order."
    stop_distance = Decimal(limits.stop_loss_points) * market.point
    if side == "BUY" and entry - stop_distance <= 0:
        return "The stop loss would be at or below zero."
    if side not in ("BUY", "SELL"):
        return "The order side must be BUY or SELL."
    return None
