"""Copy one admin order onto each connected user's own terminal."""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import utcnow
from app.models import User
from app.services.market_service import ensure_config
from app.trading_models import DemoOrder, MarketReport, ReportedPosition, TradeCommand, TradingAgent

ROOT = Path(__file__).resolve().parents[3]
STRATEGY_PATH = ROOT / "strategy-engine"
if str(STRATEGY_PATH) not in sys.path:
    sys.path.insert(0, str(STRATEGY_PATH))

from strategy_engine.risk import MarketSnapshot, RiskLimits, assess_demo_order


def broadcast_trade(db: Session, *, symbol: str, side: str, lot: Decimal) -> dict:
    symbol = symbol.upper()[:32]
    if side not in {"BUY", "SELL"}:
        raise ValueError("The side must be BUY or SELL.")
    if lot <= 0:
        raise ValueError("The lot must be greater than zero.")
    broadcast_id = uuid.uuid4()
    queued = 0
    results: list[dict] = []
    agents = db.query(TradingAgent).all()
    for agent in agents:
        user = db.get(User, agent.user_id)
        if user is None or not user.is_active:
            continue
        label = user.email
        if not _online(agent) or not agent.mt5_connected or agent.environment not in {"demo", "live"}:
            results.append({"account": label, "status": "skipped", "detail": "The terminal is not connected."})
            continue
        report = db.get(MarketReport, agent.user_id)
        if (
            report is None
            or report.symbol != symbol
            or report.bid is None
            or report.ask is None
            or report.point is None
        ):
            results.append({"account": label, "status": "skipped", "detail": "That terminal has no quote for this symbol."})
            continue
        saved, detail = _queue_copy(db, agent, report, symbol, side, lot, broadcast_id)
        if saved and detail is None:
            queued += 1
            results.append({"account": label, "status": "queued", "detail": "The order was sent to this terminal."})
        else:
            results.append({"account": label, "status": "rejected", "detail": detail or "The order was not queued."})
    return {
        "id": str(broadcast_id),
        "symbol": symbol,
        "side": side,
        "lot": float(lot),
        "queued": queued,
        "results": results,
    }


def _queue_copy(
    db: Session,
    agent: TradingAgent,
    report: MarketReport,
    symbol: str,
    side: str,
    lot: Decimal,
    broadcast_id: uuid.UUID,
) -> tuple[bool, str | None]:
    config = ensure_config(db, agent.user_id)
    key = f"control:{broadcast_id}:{agent.user_id}"
    limits = RiskLimits(
        lot_size=lot,
        stop_loss_points=config.stop_loss_points,
        take_profit_points=config.take_profit_points,
        max_open_positions=config.max_open_positions,
        max_spread_points=config.max_spread_points,
        max_daily_loss=Decimal(config.max_daily_loss),
    )
    open_positions = db.query(ReportedPosition).filter(ReportedPosition.user_id == agent.user_id).count()
    market = MarketSnapshot(
        environment=agent.environment,
        free_margin=None if agent.free_margin is None else Decimal(agent.free_margin),
        margin_required=None if report.margin_required is None else Decimal(report.margin_required),
        spread_points=None if report.spread_points is None else Decimal(report.spread_points),
        min_volume=Decimal(report.min_volume or 0),
        max_volume=Decimal(report.max_volume or 0),
        volume_step=Decimal(report.volume_step or 0),
        stops_level=int(report.stops_level or 0),
        symbol_trade_mode=report.symbol_trade_mode or "disabled",
        open_positions=open_positions,
        realized_loss_today=None if report.realized_loss_today is None else Decimal(report.realized_loss_today),
        bid=Decimal(report.bid) if report.bid is not None else None,
        ask=Decimal(report.ask) if report.ask is not None else None,
        point=Decimal(report.point) if report.point is not None else None,
    )
    reason = assess_demo_order(limits, market, side)
    if reason:
        db.add(
            DemoOrder(
                id=uuid.uuid4(),
                user_id=agent.user_id,
                idempotency_key=key,
                symbol=symbol,
                side=side,
                volume=lot,
                status="rejected",
                error=reason,
                created_at=utcnow(),
            )
        )
        db.flush()
        return True, reason
    entry = market.ask if side == "BUY" else market.bid
    assert entry is not None and market.point is not None
    distance_sl = Decimal(limits.stop_loss_points) * market.point
    distance_tp = Decimal(limits.take_profit_points) * market.point
    if side == "BUY":
        sl = entry - distance_sl
        tp = entry + distance_tp
    else:
        sl = entry + distance_sl
        tp = entry - distance_tp
    comment = hashlib.sha256(key.encode("utf-8")).hexdigest()[:29]
    command = TradeCommand(
        id=uuid.uuid4(),
        user_id=agent.user_id,
        agent_id=agent.id,
        kind="place_demo_order",
        idempotency_key=key,
        payload={
            "symbol": symbol,
            "side": side,
            "volume": str(lot),
            "sl": float(sl),
            "tp": float(tp),
            "price": float(entry),
            "comment": comment,
        },
        status="pending",
        expires_at=utcnow() + timedelta(seconds=60),
        created_at=utcnow(),
    )
    db.add(command)
    db.flush()
    db.add(
        DemoOrder(
            id=uuid.uuid4(),
            user_id=agent.user_id,
            command_id=command.id,
            idempotency_key=key,
            symbol=symbol,
            side=side,
            volume=lot,
            sl=sl,
            tp=tp,
            requested_price=entry,
            status="pending",
            created_at=utcnow(),
        )
    )
    db.flush()
    return True, None


def _online(agent: TradingAgent) -> bool:
    if agent.last_seen_at is None:
        return False
    seen = agent.last_seen_at
    if seen.tzinfo is None:
        from datetime import timezone

        seen = seen.replace(tzinfo=timezone.utc)
    return utcnow() - seen <= timedelta(seconds=get_settings().agent_offline_seconds)
