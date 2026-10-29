"""Login for the separate admin panel. These accounts are not trading users."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.security import (
    AuthError,
    create_control_token,
    hash_password,
    utcnow,
    validate_password_strength,
    verify_password,
)
from app.trading_models import ControlAdmin

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


def create_control_admin(db: Session, username: str, password: str) -> ControlAdmin:
    name = username.strip().lower()
    if _USERNAME.fullmatch(name) is None:
        raise AuthError(422, "Username must be 3 to 40 letters, numbers, dots, or dashes.")
    validate_password_strength(password)
    if db.query(ControlAdmin).filter(ControlAdmin.username == name).one_or_none() is not None:
        raise AuthError(409, "That admin username is already registered.")
    row = ControlAdmin(username=name, password_hash=hash_password(password), is_active=True, created_at=utcnow())
    db.add(row)
    db.flush()
    return row


def login_control(db: Session, username: str, password: str) -> str:
    name = username.strip().lower()
    row = db.query(ControlAdmin).filter(ControlAdmin.username == name).one_or_none()
    if row is None or not verify_password(row.password_hash, password):
        raise AuthError(401, "The admin username or password is wrong.")
    if not row.is_active:
        raise AuthError(403, "This admin account is disabled.")
    return create_control_token(admin_id=str(row.id))
