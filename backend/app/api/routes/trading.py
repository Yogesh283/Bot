from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.credentials import encrypt_secret
from app.core.security import hash_token, new_token, utcnow
from app.database import get_db
from app.models import User
from app.services.account_link import confirm_broker, confirm_deposit
from app.services.bot_service import set_demo_trading, start_bot, stop_bot, update_settings
from app.services.market_service import queue_explicit_demo_order
from app.trading_models import Mt5Credential, TradingAgent

router = APIRouter(tags=["trading"])


class DemoTradingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool
    confirm: str = ""


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str | None = None
    timeframe: str | None = None
    fast_period: int | None = Field(default=None, ge=2, le=200)
    slow_period: int | None = Field(default=None, ge=3, le=400)
    lot_size: float | None = Field(default=None, gt=0, le=100)
    stop_loss_points: int | None = Field(default=None, ge=1, le=100000)
    take_profit_points: int | None = Field(default=None, ge=1, le=100000)
    max_open_positions: int | None = Field(default=None, ge=1, le=50)
    max_spread_points: int | None = Field(default=None, ge=1, le=100000)
    max_daily_loss: float | None = Field(default=None, gt=0, le=1000000)


@router.post("/agents/enroll")
def enroll(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    raw = new_token()
    agent = db.query(TradingAgent).filter(TradingAgent.user_id == user.id).one_or_none()
    if agent is None:
        agent = TradingAgent(user_id=user.id, token_hash=hash_token(raw), created_at=utcnow())
        db.add(agent)
    else:
        agent.token_hash = hash_token(raw)
    db.flush()
    return {
        "agent_id": str(agent.id),
        "token": raw,
        "message": "Copy this agent token now. It is stored only as a hash and will not be shown again.",
    }


@router.post("/bot/start")
def start(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    start_bot(db, user)
    return {"bot_status": "running", "trading_enabled": True}


@router.post("/bot/stop")
def stop(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stop_bot(db, user)
    return {
        "bot_status": "stopped",
        "message": "New entries are stopped. Open positions were not closed.",
    }


@router.post("/bot/demo-trading")
def demo_trading(
    body: DemoTradingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if body.enabled and body.confirm != "DEMO":
        raise HTTPException(status_code=422, detail="Type DEMO to allow Demo orders. Nothing was sent.")
    set_demo_trading(db, user, body.enabled)
    return {"demo_trading_enabled": body.enabled, "trading_enabled": True}


@router.post("/bot/settings")
def settings(
    body: SettingsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    update_settings(db, user, body.model_dump(exclude_none=True))
    return {"saved": True}


class Mt5SessionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    server: str = Field(min_length=1, max_length=120)
    login: int = Field(gt=0)
    password: str = Field(min_length=1, max_length=128)
    terminal_path: str | None = Field(default=None, max_length=260)


@router.get("/mt5/session")
def read_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    row = db.get(Mt5Credential, user.id)
    if row is None:
        return {"stored": False, "login": None, "server": None}
    return {"stored": True, "login": row.account_login, "server": row.server_name}


@router.post("/mt5/session")
def save_session(
    body: Mt5SessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Mt5Credential, user.id)
    ciphertext = encrypt_secret(body.password)
    if row is None:
        row = Mt5Credential(
            user_id=user.id,
            account_login=body.login,
            server_name=body.server.strip(),
            password_ciphertext=ciphertext,
            terminal_path=body.terminal_path,
            updated_at=utcnow(),
        )
        db.add(row)
    else:
        row.account_login = body.login
        row.server_name = body.server.strip()
        row.password_ciphertext = ciphertext
        row.terminal_path = body.terminal_path
        row.updated_at = utcnow()
    db.flush()
    return {"stored": True, "login": row.account_login, "server": row.server_name}


class DepositRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    confirm: str = ""


class BrokerLinkRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    network: str = Field(min_length=1, max_length=120)
    login: int = Field(gt=0)
    mobile: str = Field(pattern=r"^[0-9]{10,15}$")
    password: str = Field(min_length=1, max_length=128)
    vpn_username: str = Field(min_length=1, max_length=120)
    vpn_password: str = Field(min_length=1, max_length=128)
    vps_username: str = Field(min_length=1, max_length=120)
    vps_password: str = Field(min_length=1, max_length=128)
    confirm: str = ""


@router.post("/account/deposit")
def account_deposit(
    body: DepositRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Record a 100 INR deposit for this user. No card is charged and no order is sent."""
    if body.confirm != "DEPOSIT":
        raise HTTPException(status_code=422, detail="Type DEPOSIT to record 100 rupees. Nothing was saved.")
    view = confirm_deposit(db, user)
    view["trading_enabled"] = True
    return view


@router.post("/broker/confirm")
def broker_confirm(
    body: BrokerLinkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Save this user's broker, VPN, and VPS logins. Passwords are not returned."""
    if body.confirm != "CONFIRM":
        raise HTTPException(status_code=422, detail="Type CONFIRM to save the broker link. Nothing was saved.")
    view = confirm_broker(
        db,
        user,
        network=body.network,
        login=body.login,
        mobile=body.mobile,
        password=body.password,
        vpn_username=body.vpn_username,
        vpn_password=body.vpn_password,
        vps_username=body.vps_username,
        vps_password=body.vps_password,
    )
    view["trading_enabled"] = True
    return view


class DemoTestOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")

    side: str = Field(pattern="^(BUY|SELL)$")
    confirm: str = ""


@router.post("/bot/demo-order")
def demo_test_order(
    body: DemoTestOrder,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Queue one Demo order for this user only. Nothing is sent unless confirm is DEMO."""
    if body.confirm != "DEMO":
        raise HTTPException(status_code=422, detail="Type DEMO to queue one Demo order. Nothing was sent.")
    agent = db.query(TradingAgent).filter(TradingAgent.user_id == user.id).one_or_none()
    if agent is None:
        raise HTTPException(status_code=409, detail="The trading agent is offline. Nothing was sent.")
    saved, reason = queue_explicit_demo_order(db, agent, side=body.side)
    if not saved:
        raise HTTPException(status_code=409, detail=reason or "The order was not queued.")
    return {"queued": reason is None, "side": body.side, "error": reason, "trading_enabled": True}
