from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, false, func, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import JSON_TYPE, UUID_TYPE


class TradingAgent(Base):
    __tablename__ = "trading_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mt5_connected: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    account_login: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    server_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    environment: Mapped[str] = mapped_column(String(20), default="unknown", server_default=text("'unknown'"))
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    equity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    free_margin: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    setup_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Mt5Credential(Base):
    """Broker login stored for the Windows agent. The password column is ciphertext only."""

    __tablename__ = "mt5_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    account_login: Mapped[int] = mapped_column(BigInteger)
    server_name: Mapped[str] = mapped_column(String(120))
    password_ciphertext: Mapped[str] = mapped_column(Text)
    account_mode: Mapped[str] = mapped_column(String(8), default="demo", server_default=text("'demo'"))
    terminal_path: Mapped[str | None] = mapped_column(String(260), nullable=True)
    mobile_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vpn_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vpn_password_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    vps_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vps_password_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccountDeposit(Base):
    """A recorded 100 INR app deposit. No card or bank payment is stored."""

    __tablename__ = "account_deposits"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="confirmed", server_default=text("'confirmed'"))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BotConfig(Base):
    __tablename__ = "bot_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="stopped", server_default=text("'stopped'"))
    symbol: Mapped[str] = mapped_column(String(32), default="XAUUSD", server_default=text("'XAUUSD'"))
    timeframe: Mapped[str] = mapped_column(String(8), default="M15", server_default=text("'M15'"))
    fast_period: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    slow_period: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    lot_size: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.01"), server_default="0.01")
    stop_loss_points: Mapped[int] = mapped_column(Integer, default=300, server_default="300")
    take_profit_points: Mapped[int] = mapped_column(Integer, default=600, server_default="600")
    max_open_positions: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    max_spread_points: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    max_daily_loss: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("100"), server_default="100")
    demo_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketReport(Base):
    __tablename__ = "market_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    spread_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    point: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    min_volume: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_volume: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume_step: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    stops_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    symbol_trade_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    margin_required: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    realized_loss_today: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    candles: Mapped[list] = mapped_column(JSON_TYPE, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    signal: Mapped[str] = mapped_column(String(16))
    candle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fast_ma: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    slow_ma: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    data_status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TradeCommand(Base):
    __tablename__ = "trade_commands"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_trade_commands_idempotency"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("trading_agents.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict] = mapped_column(JSON_TYPE)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default=text("'pending'"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemoOrder(Base):
    __tablename__ = "demo_orders"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_demo_orders_idempotency"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    command_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, ForeignKey("trade_commands.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    volume: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    sl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    requested_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    retcode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deal_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    """Local plan row. FakeProvider writes it. No payment secret is stored."""

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    plan: Mapped[str] = mapped_column(String(40), default="demo", server_default=text("'demo'"))
    status: Mapped[str] = mapped_column(String(20), default="active", server_default=text("'active'"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminSignal(Base):
    __tablename__ = "admin_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    sl_points: Mapped[int] = mapped_column(Integer)
    tp_mode: Mapped[str] = mapped_column(String(20))
    rr: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    tp_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="", server_default=text("''"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSignal(Base):
    __tablename__ = "user_signals"
    __table_args__ = (UniqueConstraint("signal_id", "user_id", name="uq_user_signals_once"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("admin_signals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default=text("'pending'"))
    retcode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TradeSample(Base):
    """One filled order kept so accuracy can be counted after it closes. Profit is not predicted."""

    __tablename__ = "trade_samples"
    __table_args__ = (UniqueConstraint("user_id", "order_ticket", name="uq_trade_samples_ticket"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_ticket: Mapped[int] = mapped_column(BigInteger)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    volume: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default=text("'open'"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlAdmin(Base):
    """Desk login for the separate admin panel. This is not a trading user."""

    __tablename__ = "control_admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportedPosition(Base):
    __tablename__ = "reported_positions"
    __table_args__ = (UniqueConstraint("user_id", "ticket", name="uq_reported_positions_ticket"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticket: Mapped[int] = mapped_column(BigInteger)
    symbol: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    volume: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    price_open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    sl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
