from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import InvalidToken, as_utc, decode_access_token, utcnow
from app.database import get_db
from app.models import RefreshToken, User


def client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    raw = authorization.split(" ", 1)[1].strip()
    if not raw:
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(raw)
        user_id = uuid.UUID(str(payload["sub"]))
        session_id = uuid.UUID(str(payload["sid"]))
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"}) from exc

    user = db.get(User, user_id)
    session = db.get(RefreshToken, session_id)
    now = utcnow()
    if user is None or session is None or session.user_id != user.id:
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")
    expires_at = as_utc(session.expires_at)
    if session.revoked_at is not None or expires_at is None or expires_at <= now:
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user
