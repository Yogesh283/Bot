from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy.orm import Session

from app.api.deps import clear_refresh_cookie, client_ip, set_refresh_cookie
from app.core.security import AuthError
from app.database import get_db
from app.schemas import EmailRequest, LoginRequest, MessageResponse, RegisterRequest, ResetPasswordRequest, TokenRequest, TokenResponse
from app.services.auth_service import (
    login_user,
    register_user,
    request_password_reset,
    reset_password,
    revoke_presented,
    rotate_refresh,
    verify_email,
)
from app.services.emailer import EmailSender, get_email_sender
from app.services.rate_limit import get_redis

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MessageResponse, status_code=201)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    redis: Redis | None = Depends(get_redis),
    mailer: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    register_user(
        db,
        redis,
        mailer,
        email=str(body.email),
        password=body.password,
        full_name=body.full_name,
        ip=client_ip(request),
    )
    return MessageResponse(
        message="Account created. In local development, open the verification link printed in the API console."
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify(
    body: TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    verify_email(db, body.token, client_ip(request))
    return MessageResponse(message="Email verified. You can sign in.")


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis: Redis | None = Depends(get_redis),
) -> TokenResponse:
    issued = login_user(db, redis, email=str(body.email), password=body.password, ip=client_ip(request))
    set_refresh_cookie(response, issued.refresh_raw)
    return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse | JSONResponse:
    from app.config import get_settings

    raw = request.cookies.get(get_settings().cookie_name)
    try:
        issued = rotate_refresh(db, raw)
    except AuthError as exc:
        rejected = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        clear_refresh_cookie(rejected)
        return rejected
    set_refresh_cookie(response, issued.refresh_raw)
    return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    from app.config import get_settings

    raw = request.cookies.get(get_settings().cookie_name)
    revoke_presented(db, raw, client_ip(request))
    clear_refresh_cookie(response)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: EmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    mailer: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    request_password_reset(db, mailer, email=str(body.email), ip=client_ip(request))
    return MessageResponse(message="If an account exists for that email, a reset link has been issued.")


@router.post("/reset-password", response_model=MessageResponse)
def reset(
    body: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageResponse:
    reset_password(db, raw_token=body.token, new_password=body.password, ip=client_ip(request))
    return MessageResponse(message="Password updated. Sign in with the new password.")
