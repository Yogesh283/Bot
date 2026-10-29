"""Routes for the separate admin panel. Trading-user tokens are not accepted."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.security import InvalidToken, decode_control_token
from app.database import get_db
from app.services.control_auth import login_control
from app.services.control_trades import broadcast_trade
from app.trading_models import ControlAdmin

router = APIRouter(prefix="/control", tags=["control"])


class ControlLogin(BaseModel):
    model_config = ConfigDict(extra="ignore")

    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class ControlTrade(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(pattern="^(BUY|SELL)$")
    lot: float = Field(gt=0, le=100)


def get_control_admin(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> ControlAdmin:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Admin sign-in required.")
    raw = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_control_token(raw)
        admin_id = uuid.UUID(str(payload["sub"]))
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Admin sign-in required.") from exc
    admin = db.get(ControlAdmin, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin sign-in required.")
    return admin


@router.post("/login")
def login(body: ControlLogin, db: Session = Depends(get_db)) -> dict:
    token = login_control(db, body.username, body.password)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(admin: ControlAdmin = Depends(get_control_admin)) -> dict:
    return {"username": admin.username}


@router.post("/trades")
def create_trade(
    body: ControlTrade,
    _admin: ControlAdmin = Depends(get_control_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return broadcast_trade(db, symbol=body.symbol, side=body.side.upper(), lot=Decimal(str(body.lot)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
