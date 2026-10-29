"""Deposit and broker link for one user. Passwords are stored as ciphertext only."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.credentials import encrypt_secret
from app.core.security import utcnow
from app.models import User
from app.services.market_service import ensure_config
from app.trading_models import AccountDeposit, Mt5Credential

DEPOSIT_INR = Decimal("100.00")


def link_view(db: Session, user_id) -> dict:
    deposit = db.get(AccountDeposit, user_id)
    row = db.get(Mt5Credential, user_id)
    confirmed = row is not None and row.confirmed_at is not None
    ready = confirmed and deposit is not None and deposit.status == "confirmed" and bool(row.vpn_username) and bool(row.vps_username)
    return {
        "deposit_inr": 100,
        "deposit_status": deposit.status if deposit is not None else "pending",
        "broker_confirmed": confirmed,
        "broker_server": row.server_name if confirmed else None,
        "broker_login": row.account_login if confirmed else None,
        "broker_mobile": row.mobile_number if confirmed else None,
        "vpn_username": row.vpn_username if confirmed else None,
        "vps_username": row.vps_username if confirmed else None,
        "execution": "linked" if ready else "waiting",
    }


def confirm_deposit(db: Session, user: User) -> dict:
    row = db.get(AccountDeposit, user.id)
    now = utcnow()
    if row is None:
        row = AccountDeposit(user_id=user.id, amount_inr=DEPOSIT_INR, status="confirmed", confirmed_at=now)
        db.add(row)
    else:
        row.amount_inr = DEPOSIT_INR
        row.status = "confirmed"
        row.confirmed_at = now
    db.flush()
    return link_view(db, user.id)


def confirm_broker(
    db: Session,
    user: User,
    *,
    network: str,
    login: int,
    mobile: str,
    password: str,
    vpn_username: str,
    vpn_password: str,
    vps_username: str,
    vps_password: str,
) -> dict:
    deposit = db.get(AccountDeposit, user.id)
    if deposit is None or deposit.status != "confirmed":
        raise HTTPException(status_code=409, detail="Confirm the 100 rupee deposit first. Nothing was saved.")
    row = db.get(Mt5Credential, user.id)
    now = utcnow()
    if row is None:
        row = Mt5Credential(
            user_id=user.id,
            account_login=login,
            server_name=network.strip(),
            password_ciphertext=encrypt_secret(password),
            mobile_number=mobile,
            vpn_username=vpn_username.strip(),
            vpn_password_ciphertext=encrypt_secret(vpn_password),
            vps_username=vps_username.strip(),
            vps_password_ciphertext=encrypt_secret(vps_password),
            confirmed_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.account_login = login
        row.server_name = network.strip()
        row.password_ciphertext = encrypt_secret(password)
        row.mobile_number = mobile
        row.vpn_username = vpn_username.strip()
        row.vpn_password_ciphertext = encrypt_secret(vpn_password)
        row.vps_username = vps_username.strip()
        row.vps_password_ciphertext = encrypt_secret(vps_password)
        row.confirmed_at = now
        row.updated_at = now
    config = ensure_config(db, user.id)
    config.demo_trading_enabled = True
    config.updated_at = now
    db.flush()
    return link_view(db, user.id)
