from __future__ import annotations

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
STRATEGY_PATH = ROOT / "strategy-engine"
if str(STRATEGY_PATH) not in sys.path:
    sys.path.insert(0, str(STRATEGY_PATH))

from strategy_engine.moving_average import MovingAverageConfig

from app.config import get_settings
from app.core.security import utcnow
from app.models import User
from app.services.account_link import link_view
from app.services.accuracy import accuracy_view
from app.services.market_service import ALLOWED_TIMEFRAMES, ensure_config
from app.services.subscription import enforce_subscriptions, subscription_is_active, subscription_view
from app.trading_models import AnalysisRecord, BotConfig, DemoOrder, MarketReport, ReportedPosition, TradeCommand, TradingAgent


def build_dashboard(db: Session, user: User) -> dict:
    enforce_subscriptions(db)
    agent = db.query(TradingAgent).filter(TradingAgent.user_id == user.id).one_or_none()
    config = db.get(BotConfig, user.id)
    online = _agent_is_online(agent)
    mt5_status = "not_configured"
    setup = None
    if agent is not None:
        setup = agent.setup_requirement
        if online and agent.mt5_connected and agent.environment in {"demo", "live"}:
            mt5_status = "connected"
        elif agent.last_seen_at is not None:
            mt5_status = "setup_required"
    positions = db.query(ReportedPosition).filter(ReportedPosition.user_id == user.id).all()
    orders = (
        db.query(DemoOrder)
        .filter(DemoOrder.user_id == user.id)
        .order_by(DemoOrder.created_at.desc())
        .limit(20)
        .all()
    )
    latest = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.user_id == user.id)
        .order_by(AnalysisRecord.created_at.desc())
        .first()
    )
    report = db.get(MarketReport, user.id)
    floating = sum((float(row.profit) for row in positions), 0.0) if positions else None
    notifications = [
        "Buy and Sell send an order for this account.",
    ]
    if not online:
        notifications.append("The trading agent is offline. Start Bot is rejected until the Windows agent sends a heartbeat.")
    elif setup:
        notifications.append(setup)
    if config and not config.demo_trading_enabled:
        notifications.append("Demo trading is off, so signals are recorded and no order is sent.")
    subscription = subscription_view(db, user.id)
    if subscription["status"] != "active":
        notifications.append("The subscription is not active, so the bot cannot start.")
    return {
        "agent_status": "online" if online else "offline",
        "mt5_status": mt5_status,
        "bot_status": config.status if config else "stopped",
        "environment": agent.environment if agent is not None and agent.environment in {"demo", "live"} else "demo",
        "balance": None if agent is None or agent.balance is None else float(agent.balance),
        "equity": None if agent is None or agent.equity is None else float(agent.equity),
        "floating_pnl": floating,
        "daily_pnl": None,
        "open_positions": [
            {
                "ticket": row.ticket,
                "symbol": row.symbol,
                "side": row.side,
                "volume": float(row.volume),
                "price_open": float(row.price_open),
                "sl": None if row.sl is None else float(row.sl),
                "tp": None if row.tp is None else float(row.tp),
                "profit": float(row.profit),
            }
            for row in positions
        ],
        "closed_trades": [_order_view(row) for row in orders if row.status == "filled"],
        "orders": [_order_view(row) for row in orders],
        "notifications": notifications,
        "trading_enabled": True,
        "bid": None if report is None or report.bid is None else float(report.bid),
        "ask": None if report is None or report.ask is None else float(report.ask),
        "lot_size": float(config.lot_size) if config else 0.01,
        "stop_loss_points": config.stop_loss_points if config else 300,
        "take_profit_points": config.take_profit_points if config else 600,
        "demo_trading_enabled": bool(config and config.demo_trading_enabled),
        "setup_requirement": setup,
        "symbol": config.symbol if config else "XAUUSD",
        "timeframe": config.timeframe if config else "M15",
        "subscription": subscription,
        "account_link": link_view(db, user.id),
        "accuracy": accuracy_view(db, user.id),
        "analysis": None
        if latest is None
        else {
            "signal": latest.signal,
            "symbol": latest.symbol,
            "timeframe": latest.timeframe,
            "candle_time": latest.candle_time,
            "fast_ma": None if latest.fast_ma is None else float(latest.fast_ma),
            "slow_ma": None if latest.slow_ma is None else float(latest.slow_ma),
            "data_status": latest.data_status,
            "detail": latest.detail,
        },
    }


def start_bot(db: Session, user: User) -> None:
    enforce_subscriptions(db)
    agent = db.query(TradingAgent).filter(TradingAgent.user_id == user.id).one_or_none()
    if not _agent_is_online(agent):
        detail = "The trading agent is offline. Start the Windows agent beside MetaTrader 5. The bot was not started."
        raise HTTPException(status_code=409, detail=detail)
    assert agent is not None
    if not agent.mt5_connected or agent.environment not in {"demo", "live"}:
        raise HTTPException(
            status_code=409,
            detail=agent.setup_requirement or "MT5 is not connected. The bot was not started.",
        )
    config = ensure_config(db, user.id)
    problem = MovingAverageConfig(config.fast_period, config.slow_period).problem()
    if problem or config.timeframe not in ALLOWED_TIMEFRAMES:
        raise HTTPException(status_code=409, detail=problem or "Choose a supported timeframe. The bot was not started.")
    if not subscription_is_active(db, user.id):
        raise HTTPException(status_code=402, detail="An active subscription is required. The bot was not started.")
    config.status = "running"
    config.demo_trading_enabled = True
    config.updated_at = utcnow()


def stop_bot(db: Session, user: User) -> None:
    config = ensure_config(db, user.id)
    config.status = "stopped"
    config.updated_at = utcnow()
    (
        db.query(TradeCommand)
        .filter(TradeCommand.user_id == user.id, TradeCommand.status == "pending")
        .update({TradeCommand.status: "cancelled"}, synchronize_session=False)
    )


def set_demo_trading(db: Session, user: User, enabled: bool) -> None:
    config = ensure_config(db, user.id)
    config.demo_trading_enabled = enabled
    config.updated_at = utcnow()


def update_settings(db: Session, user: User, body: dict) -> None:
    config = ensure_config(db, user.id)
    if "symbol" in body and body["symbol"]:
        config.symbol = str(body["symbol"]).upper()[:32]
    if "timeframe" in body:
        timeframe = str(body["timeframe"]).upper()
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise HTTPException(status_code=422, detail="Unsupported timeframe.")
        config.timeframe = timeframe
    for field in ("fast_period", "slow_period", "stop_loss_points", "take_profit_points", "max_open_positions", "max_spread_points"):
        if field in body and body[field] is not None:
            setattr(config, field, int(body[field]))
    if body.get("lot_size") is not None:
        config.lot_size = Decimal(str(body["lot_size"]))
    if body.get("max_daily_loss") is not None:
        config.max_daily_loss = Decimal(str(body["max_daily_loss"]))
    problem = MovingAverageConfig(config.fast_period, config.slow_period).problem()
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    config.updated_at = utcnow()


def _agent_is_online(agent: TradingAgent | None) -> bool:
    if agent is None or agent.last_seen_at is None:
        return False
    seen = agent.last_seen_at
    if seen.tzinfo is None:
        from datetime import timezone

        seen = seen.replace(tzinfo=timezone.utc)
    return utcnow() - seen <= timedelta(seconds=get_settings().agent_offline_seconds)


def _order_view(row: DemoOrder) -> dict:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "side": row.side,
        "volume": float(row.volume),
        "sl": None if row.sl is None else float(row.sl),
        "tp": None if row.tp is None else float(row.tp),
        "status": row.status,
        "retcode": row.retcode,
        "order_ticket": row.order_ticket,
        "deal_ticket": row.deal_ticket,
        "error": row.error,
        "created_at": row.created_at,
    }
