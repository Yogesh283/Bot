from __future__ import annotations

import uuid

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import utcnow
from app.database import get_db
from app.models import AuditLog, RefreshToken, User
from app.schemas import AuditPublic, HealthReport, UserPublic
from app.services.audit import add_audit
from app.services.market_service import queue_explicit_demo_order
from app.services.signals import publish_admin_signal, signal_counts
from app.services.rate_limit import get_redis
from app.trading_models import TradingAgent

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health", response_model=HealthReport)
def health(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    redis: Redis | None = Depends(get_redis),
) -> HealthReport:
    database_status: Literal["ok", "unavailable"] = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    redis_status: Literal["ok", "unavailable"] = "ok" if redis is not None else "unavailable"
    return HealthReport(database=database_status, redis=redis_status)


@router.get("/users", response_model=list[UserPublic])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/audit", response_model=list[AuditPublic])
def list_audit(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/users/{user_id}/disable", response_model=UserPublic)
def disable_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    return _set_active(db, admin, user_id, active=False)


@router.post("/users/{user_id}/enable", response_model=UserPublic)
def enable_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    return _set_active(db, admin, user_id, active=True)


class AdminSignalIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(BUY|SELL)$")
    sl_points: int = Field(ge=1, le=100000)
    tp_mode: str = Field(pattern="^(fixed_rr|atr|manual)$")
    rr: float = Field(default=2.0, gt=0, le=20)
    tp_points: int | None = Field(default=None, ge=1, le=100000)
    note: str = Field(default="", max_length=300)


@router.post("/signals")
def create_signal(
    body: AdminSignalIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        signal, recipients = publish_admin_signal(db, admin, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_audit(db, user_id=admin.id, action="admin.signal", detail=f"Published a Demo {signal.side} signal for {signal.symbol}.", ip=None)
    return {"id": signal.id, "recipients": recipients, "trading_enabled": True}


@router.get("/signals")
def list_signals(_admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return {"signals": signal_counts(db), "trading_enabled": True}


class AdminDemoOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")

    side: str = Field(pattern="^(BUY|SELL)$")


@router.post("/users/{user_id}/demo-orders")
def create_demo_order(
    user_id: uuid.UUID,
    body: AdminDemoOrder,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    agent = db.query(TradingAgent).filter(TradingAgent.user_id == user_id).one_or_none()
    if agent is None:
        raise HTTPException(status_code=409, detail="The trading agent is offline. Nothing was sent.")
    saved, reason = queue_explicit_demo_order(db, agent, side=body.side)
    if not saved:
        raise HTTPException(status_code=409, detail=reason or "The order was not queued.")
    if reason is None:
        add_audit(db, user_id=admin.id, action="admin.demo_order", detail=f"Queued a Demo {body.side} order.", ip=None)
    return {"queued": reason is None, "error": reason, "trading_enabled": True}


def _set_active(db: Session, admin: User, user_id: uuid.UUID, *, active: bool) -> User:
    if admin.id == user_id and not active:
        raise HTTPException(status_code=400, detail="You cannot disable your own administrator account.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    now = utcnow()
    user.is_active = active
    user.updated_at = now
    if not active:
        (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .update({RefreshToken.revoked_at: now}, synchronize_session=False)
        )
    add_audit(
        db,
        user_id=admin.id,
        action="admin.disable_user" if not active else "admin.enable_user",
        detail=f"{'Disabled' if not active else 'Enabled'} account {user.email}.",
        ip=None,
    )
    return user
