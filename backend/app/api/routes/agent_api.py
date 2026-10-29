from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.database import get_db
from app.models import User
from app.services.market_service import apply_command_result, ingest_market, pending_commands, record_heartbeat
from app.services.signals import acknowledge_signal, pending_signals_for_agent
from app.services.subscription import enforce_subscriptions
from app.trading_models import Mt5Credential, TradeCommand, TradingAgent

router = APIRouter(prefix="/agent", tags=["agent"])


class HeartbeatIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mt5_connected: bool = False
    setup_requirement: str | None = None
    account_login: int | None = None
    server_name: str | None = None
    trade_environment: str = "unknown"
    balance: float | None = None
    equity: float | None = None
    free_margin: float | None = None
    last_error: str | None = None


class MarketIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str
    timeframe: str
    candles: list[dict] = []
    positions: list[dict] = []
    spread_points: float | None = None
    bid: float | None = None
    ask: float | None = None
    point: float | None = None
    min_volume: float | None = None
    max_volume: float | None = None
    volume_step: float | None = None
    stops_level: int | None = None
    symbol_trade_mode: str | None = None
    margin_required: float | None = None
    realized_loss_today: float | None = None


class ResultIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    retcode: int | None = None
    order_ticket: int | None = None
    deal_ticket: int | None = None
    price: float | None = None
    error: str | None = None


def get_agent(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> TradingAgent:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Agent token required.")
    raw = authorization.split(" ", 1)[1].strip()
    agent = db.query(TradingAgent).filter(TradingAgent.token_hash == hash_token(raw)).one_or_none()
    if agent is None:
        raise HTTPException(status_code=401, detail="Agent token required.")
    user = db.get(User, agent.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")
    return agent


@router.get("/session")
def session(agent: TradingAgent = Depends(get_agent), db: Session = Depends(get_db)) -> dict:
    row = db.get(Mt5Credential, agent.user_id)
    if row is None:
        return {"user_id": str(agent.user_id), "login": None, "server": None, "password_ciphertext": None, "account_mode": "demo", "terminal_path": None}
    return {
        "user_id": str(agent.user_id),
        "login": row.account_login,
        "server": row.server_name,
        "password_ciphertext": row.password_ciphertext,
        "account_mode": row.account_mode if row.account_mode in {"demo", "live"} else "demo",
        "terminal_path": row.terminal_path,
        "vpn_username": row.vpn_username,
        "vpn_password_ciphertext": row.vpn_password_ciphertext,
        "vps_username": row.vps_username,
        "vps_password_ciphertext": row.vps_password_ciphertext,
    }


@router.post("/heartbeat")
def heartbeat(body: HeartbeatIn, agent: TradingAgent = Depends(get_agent), db: Session = Depends(get_db)) -> dict:
    record_heartbeat(db, agent, body.model_dump())
    enforce_subscriptions(db)
    return {"ok": True}


class SignalAck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket: int | None = None
    retcode: int | None = None
    reasons: list[str] = []


@router.get("/signals")
def agent_signals(agent: TradingAgent = Depends(get_agent), db: Session = Depends(get_db)) -> dict:
    return {"signals": pending_signals_for_agent(db, agent.user_id)}


@router.post("/signals/{user_signal_id}/ack")
def agent_signal_ack(
    user_signal_id: uuid.UUID,
    body: SignalAck,
    agent: TradingAgent = Depends(get_agent),
    db: Session = Depends(get_db),
) -> dict:
    saved = acknowledge_signal(db, agent.user_id, user_signal_id, body.model_dump())
    if not saved:
        raise HTTPException(status_code=404, detail="Signal not found.")
    return saved


@router.get("/work")
def work(agent: TradingAgent = Depends(get_agent), db: Session = Depends(get_db)) -> dict:
    from app.services.market_service import ensure_config

    config = ensure_config(db, agent.user_id)
    return {
        "bot_status": config.status,
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "lot_size": float(config.lot_size),
        "demo_trading_enabled": config.demo_trading_enabled,
        "max_open_positions": config.max_open_positions,
        "max_spread_points": config.max_spread_points,
        "max_daily_loss": float(config.max_daily_loss),
        "free_margin": None if agent.free_margin is None else float(agent.free_margin),
        "environment": "demo",
    }


@router.post("/market")
def market(body: MarketIn, agent: TradingAgent = Depends(get_agent), db: Session = Depends(get_db)) -> dict:
    record = ingest_market(db, agent, body.model_dump())
    return {
        "signal": record.signal,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "candle_time": record.candle_time,
        "fast_ma": None if record.fast_ma is None else float(record.fast_ma),
        "slow_ma": None if record.slow_ma is None else float(record.slow_ma),
        "data_status": record.data_status,
        "detail": record.detail,
    }


@router.get("/commands")
def commands(agent: TradingAgent = Depends(get_agent), db: Session = Depends(get_db)) -> dict:
    rows = pending_commands(db, agent)
    return {
        "commands": [
            {"id": str(row.id), "kind": row.kind, "status": row.status, "payload": row.payload}
            for row in rows
        ]
    }


@router.post("/commands/{command_id}/result")
def command_result(
    command_id: uuid.UUID,
    body: ResultIn,
    agent: TradingAgent = Depends(get_agent),
    db: Session = Depends(get_db),
) -> dict:
    command = db.get(TradeCommand, command_id)
    if command is None or command.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Command not found.")
    if command.status == "cancelled" and not (body.order_ticket or body.deal_ticket):
        return {"saved": True}
    apply_command_result(db, command, body.model_dump())
    return {"saved": True}
