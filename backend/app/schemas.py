from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str = Field(min_length=10, max_length=256)


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=1, max_length=128)


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Literal["user", "admin"]
    is_active: bool
    email_verified: bool
    created_at: datetime


class AuditPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    detail: str
    ip_address: str | None
    created_at: datetime
    user_id: uuid.UUID | None = None


class AnalysisView(BaseModel):
    signal: Literal["BUY", "SELL", "NO_SIGNAL"] | None = None
    symbol: str | None = None
    timeframe: str | None = None
    candle_time: datetime | None = None
    fast_ma: float | None = None
    slow_ma: float | None = None
    data_status: Literal["ok", "missing", "stale", "invalid"] | None = None
    detail: str | None = None


class PositionView(BaseModel):
    ticket: int
    symbol: str
    side: str
    volume: float
    price_open: float
    sl: float | None = None
    tp: float | None = None
    profit: float


class OrderView(BaseModel):
    id: uuid.UUID
    symbol: str
    side: str
    volume: float
    sl: float | None = None
    tp: float | None = None
    status: str
    retcode: int | None = None
    order_ticket: int | None = None
    deal_ticket: int | None = None
    error: str | None = None
    created_at: datetime


class SubscriptionView(BaseModel):
    plan: str = "none"
    status: Literal["active", "expired", "cancelled", "none"] = "none"
    expires_at: datetime | None = None


class AccuracyView(BaseModel):
    closed_trades: int = 0
    wins: int = 0
    accuracy: float | None = None


class AccountLinkView(BaseModel):
    deposit_inr: int = 100
    deposit_status: Literal["pending", "confirmed"] = "pending"
    broker_confirmed: bool = False
    broker_server: str | None = None
    broker_login: int | None = None
    broker_mobile: str | None = None
    vpn_username: str | None = None
    vps_username: str | None = None
    execution: Literal["waiting", "linked"] = "waiting"


class DashboardStatus(BaseModel):
    agent_status: Literal["offline", "online"]
    mt5_status: Literal["not_configured", "connected", "setup_required", "live_rejected"]
    bot_status: Literal["stopped", "running"]
    environment: Literal["demo", "live"]
    balance: float | None = None
    equity: float | None = None
    floating_pnl: float | None = None
    daily_pnl: float | None = None
    open_positions: list[PositionView] = []
    closed_trades: list[OrderView] = []
    orders: list[OrderView] = []
    notifications: list[str]
    trading_enabled: Literal[True] = True
    bid: float | None = None
    ask: float | None = None
    lot_size: float = 0.01
    stop_loss_points: int = 300
    take_profit_points: int = 600
    demo_trading_enabled: bool = False
    setup_requirement: str | None = None
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    subscription: SubscriptionView = SubscriptionView()
    account_link: AccountLinkView = AccountLinkView()
    accuracy: AccuracyView = AccuracyView()
    analysis: AnalysisView | None = None


class HealthReport(BaseModel):
    api: Literal["ok"] = "ok"
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]
    phase: Literal[1] = 1
    trading_enabled: Literal[True] = True
