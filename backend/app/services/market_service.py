from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
STRATEGY_PATH = ROOT / "strategy-engine"
if str(STRATEGY_PATH) not in sys.path:
    sys.path.insert(0, str(STRATEGY_PATH))

from strategy_engine.alarm import raise_alarm
from strategy_engine.moving_average import MovingAverageConfig, analyze_closes
from strategy_engine.risk import MarketSnapshot, RiskLimits, assess_demo_order

from app.core.security import utcnow
from app.trading_models import AnalysisRecord, BotConfig, DemoOrder, MarketReport, ReportedPosition, TradeCommand, TradeSample, TradingAgent

ALLOWED_TIMEFRAMES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


def ensure_config(db: Session, user_id: uuid.UUID) -> BotConfig:
    config = db.get(BotConfig, user_id)
    if config is None:
        config = BotConfig(user_id=user_id, updated_at=utcnow())
        db.add(config)
        db.flush()
    return config


def record_heartbeat(db: Session, agent: TradingAgent, body: dict) -> None:
    agent.last_seen_at = utcnow()
    agent.mt5_connected = bool(body.get("mt5_connected"))
    agent.setup_requirement = _clean(body.get("setup_requirement"))
    agent.account_login = body.get("account_login")
    agent.server_name = _clean(body.get("server_name"))
    environment = body.get("trade_environment") or "unknown"
    agent.environment = environment if environment in {"demo", "live", "unknown"} else "unknown"
    agent.balance = _decimal(body.get("balance"))
    agent.equity = _decimal(body.get("equity"))
    agent.free_margin = _decimal(body.get("free_margin"))
    agent.last_error = _clean(body.get("last_error"))


def ingest_market(db: Session, agent: TradingAgent, body: dict) -> AnalysisRecord:
    config = ensure_config(db, agent.user_id)
    symbol = str(body.get("symbol") or config.symbol).upper()
    timeframe = str(body.get("timeframe") or config.timeframe).upper()
    candles = body.get("candles") or []
    closes = [float(item["close"]) for item in candles if "close" in item]
    candle_time = _parse_time(candles[-1].get("time")) if candles else None
    analysis = analyze_closes(
        closes,
        candle_time,
        MovingAverageConfig(config.fast_period, config.slow_period),
        timeframe=timeframe,
    )
    report = db.get(MarketReport, agent.user_id)
    if report is None:
        report = MarketReport(user_id=agent.user_id, symbol=symbol, timeframe=timeframe, candles=[])
        db.add(report)
    report.symbol = symbol
    report.timeframe = timeframe
    report.spread_points = _decimal(body.get("spread_points"))
    report.bid = _decimal(body.get("bid"))
    report.ask = _decimal(body.get("ask"))
    report.point = _decimal(body.get("point"))
    report.min_volume = _decimal(body.get("min_volume"))
    report.max_volume = _decimal(body.get("max_volume"))
    report.volume_step = _decimal(body.get("volume_step"))
    report.stops_level = body.get("stops_level")
    report.symbol_trade_mode = body.get("symbol_trade_mode")
    report.margin_required = _decimal(body.get("margin_required"))
    report.realized_loss_today = _decimal(body.get("realized_loss_today"))
    report.candles = candles
    report.updated_at = utcnow()
    _replace_positions(db, agent.user_id, body.get("positions") or [])
    latest = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.user_id == agent.user_id)
        .order_by(AnalysisRecord.created_at.desc())
        .first()
    )
    same_candle = (
        latest is not None
        and latest.symbol == symbol
        and latest.timeframe == timeframe
        and latest.signal == analysis.signal
        and latest.data_status == analysis.data_status
        and latest.candle_time == analysis.candle_time
    )
    if same_candle:
        record = latest
    else:
        record = AnalysisRecord(
            id=uuid.uuid4(),
            user_id=agent.user_id,
            symbol=symbol,
            timeframe=timeframe,
            signal=analysis.signal,
            candle_time=analysis.candle_time,
            fast_ma=None if analysis.fast_ma is None else Decimal(str(round(analysis.fast_ma, 6))),
            slow_ma=None if analysis.slow_ma is None else Decimal(str(round(analysis.slow_ma, 6))),
            data_status=analysis.data_status,
            detail=analysis.detail[:300],
            created_at=utcnow(),
        )
        db.add(record)
        db.flush()
    alarm = raise_alarm(
        closes,
        candle_time,
        MovingAverageConfig(config.fast_period, config.slow_period),
        timeframe=timeframe,
    )
    if (
        config.status == "running"
        and config.demo_trading_enabled
        and alarm.side in {"BUY", "SELL"}
        and analysis.data_status == "ok"
        and analysis.signal == alarm.side
    ):
        _queue_demo_order(db, agent, config, report, record)
    return record


def _queue_demo_order(
    db: Session,
    agent: TradingAgent,
    config: BotConfig,
    report: MarketReport,
    analysis: AnalysisRecord,
    idempotency_key: str | None = None,
) -> None:
    if agent.environment not in {"demo", "live"} or not agent.mt5_connected:
        return
    if analysis.candle_time is None:
        return
    key = idempotency_key or f"{agent.user_id}:{analysis.symbol}:{analysis.candle_time.isoformat()}:{analysis.signal}"
    existing = db.query(DemoOrder).filter(DemoOrder.idempotency_key == key).one_or_none()
    if existing is not None:
        return
    limits = RiskLimits(
        lot_size=Decimal(config.lot_size),
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
        bid=None if report.bid is None else Decimal(report.bid),
        ask=None if report.ask is None else Decimal(report.ask),
        point=None if report.point is None else Decimal(report.point),
    )
    reason = assess_demo_order(limits, market, analysis.signal)
    comment = hashlib.sha256(key.encode("utf-8")).hexdigest()[:29]
    if reason:
        db.add(
            DemoOrder(
                id=uuid.uuid4(),
                user_id=agent.user_id,
                idempotency_key=key,
                symbol=analysis.symbol,
                side=analysis.signal,
                volume=limits.lot_size,
                status="rejected",
                error=reason,
                created_at=utcnow(),
            )
        )
        db.flush()
        return
    entry = market.ask if analysis.signal == "BUY" else market.bid
    assert entry is not None and market.point is not None
    distance_sl = Decimal(limits.stop_loss_points) * market.point
    distance_tp = Decimal(limits.take_profit_points) * market.point
    if analysis.signal == "BUY":
        sl = entry - distance_sl
        tp = entry + distance_tp
    else:
        sl = entry + distance_sl
        tp = entry - distance_tp
    command = TradeCommand(
        id=uuid.uuid4(),
        user_id=agent.user_id,
        agent_id=agent.id,
        kind="place_demo_order",
        idempotency_key=key,
        payload={
            "symbol": analysis.symbol,
            "side": analysis.signal,
            "volume": str(limits.lot_size),
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
            symbol=analysis.symbol,
            side=analysis.signal,
            volume=limits.lot_size,
            sl=sl,
            tp=tp,
            requested_price=entry,
            status="pending",
            created_at=utcnow(),
        )
    )
    db.flush()


def queue_explicit_demo_order(db: Session, agent: TradingAgent, *, side: str) -> tuple[bool, str | None]:
    """Queue one Demo order for this agent only. Returns whether a row was saved, and an error.

    A saved rejection stays in the order history. This function does not call the terminal
    and does not create a strategy signal.
    """
    if side not in {"BUY", "SELL"}:
        return False, "The order side must be BUY or SELL."
    config = ensure_config(db, agent.user_id)
    if not config.demo_trading_enabled:
        return False, "Demo trading is off. Nothing was sent."
    if agent.environment not in {"demo", "live"} or not agent.mt5_connected:
        return False, "The account is not connected. Nothing was sent."
    report = db.get(MarketReport, agent.user_id)
    if report is None or report.ask is None or report.bid is None:
        return False, "No market data has been published for this account. Nothing was sent."
    key = f"manual:{agent.user_id}:{uuid.uuid4()}"
    reference = AnalysisRecord(
        id=uuid.uuid4(),
        user_id=agent.user_id,
        symbol=config.symbol,
        timeframe=config.timeframe,
        signal=side,
        candle_time=utcnow(),
        data_status="ok",
        detail="Explicit Demo order. This is not a strategy signal.",
        created_at=utcnow(),
    )
    _queue_demo_order(db, agent, config, report, reference, idempotency_key=key)
    stored = db.query(DemoOrder).filter(DemoOrder.idempotency_key == key).one_or_none()
    if stored is None:
        return False, "The order was not queued."
    if stored.status == "pending":
        return True, None
    return True, stored.error or "The order was rejected."


def apply_command_result(db: Session, command: TradeCommand, body: dict) -> None:
    status = body.get("status") or "unknown"
    if status not in {"filled", "rejected", "unknown"}:
        status = "unknown"
    ticket = body.get("order_ticket")
    deal = body.get("deal_ticket")
    retcode = body.get("retcode")
    if status == "filled" and retcode is not None and (ticket or deal):
        command.status = "succeeded"
    elif status == "rejected":
        command.status = "failed"
    else:
        command.status = "unknown"
        status = "unknown"
    command.error = _clean(body.get("error"))
    command.result = {
        "status": status,
        "retcode": retcode,
        "order_ticket": ticket,
        "deal_ticket": deal,
        "price": body.get("price"),
    }
    order = db.query(DemoOrder).filter(DemoOrder.command_id == command.id).one_or_none()
    if order is None:
        return
    order.status = "filled" if command.status == "succeeded" else status
    order.retcode = retcode
    order.order_ticket = ticket
    order.deal_ticket = deal
    order.error = command.error
    if order.status == "filled" and order.order_ticket:
        _remember_sample(db, order)


def pending_commands(db: Session, agent: TradingAgent) -> list[TradeCommand]:
    now = utcnow()
    return (
        db.query(TradeCommand)
        .filter(
            TradeCommand.agent_id == agent.id,
            TradeCommand.status == "pending",
            TradeCommand.expires_at > now,
        )
        .order_by(TradeCommand.created_at.asc())
        .all()
    )


def _remember_sample(db: Session, order: DemoOrder) -> None:
    if order.order_ticket is None:
        return
    existing = (
        db.query(TradeSample)
        .filter(TradeSample.user_id == order.user_id, TradeSample.order_ticket == order.order_ticket)
        .one_or_none()
    )
    if existing is not None:
        return
    db.add(
        TradeSample(
            id=uuid.uuid4(),
            user_id=order.user_id,
            order_ticket=order.order_ticket,
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            profit=None,
            status="open",
            opened_at=utcnow(),
        )
    )


def _sync_samples(db: Session, user_id: uuid.UUID, positions: list[dict]) -> None:
    open_rows = db.query(TradeSample).filter(TradeSample.user_id == user_id, TradeSample.status == "open").all()
    by_ticket = {int(item["ticket"]): item for item in positions}
    now = utcnow()
    for row in open_rows:
        current = by_ticket.get(int(row.order_ticket))
        if current is None:
            row.status = "closed"
            row.closed_at = now
            continue
        row.profit = Decimal(str(current.get("profit") or 0))


def _replace_positions(db: Session, user_id: uuid.UUID, positions: list[dict]) -> None:
    _sync_samples(db, user_id, positions)
    db.query(ReportedPosition).filter(ReportedPosition.user_id == user_id).delete()
    for item in positions:
        db.add(
            ReportedPosition(
                id=uuid.uuid4(),
                user_id=user_id,
                ticket=int(item["ticket"]),
                symbol=str(item["symbol"]),
                side=str(item["side"]),
                volume=Decimal(str(item["volume"])),
                price_open=Decimal(str(item["price_open"])),
                sl=None if item.get("sl") is None else Decimal(str(item["sl"])),
                tp=None if item.get("tp") is None else Decimal(str(item["tp"])),
                profit=Decimal(str(item.get("profit") or 0)),
                updated_at=utcnow(),
            )
        )


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value)
    lowered = text.lower()
    if "password" in lowered or "token" in lowered:
        return "A sensitive value was removed from this message."
    return text[:500]
