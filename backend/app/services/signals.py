from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import utcnow
from app.models import User
from app.services.subscription import enforce_subscriptions, subscription_is_active
from app.trading_models import AdminSignal, BotConfig, TradingAgent, UserSignal


def _clean(value: str) -> str:
    text = value.strip()
    if "password" in text.lower() or "token" in text.lower():
        return "A sensitive value was removed from this message."
    return text[:300]


def publish_admin_signal(db: Session, admin: User, body: dict) -> tuple[AdminSignal, int]:
    enforce_subscriptions(db)
    side = str(body["side"]).upper()
    tp_mode = str(body["tp_mode"])
    if side not in {"BUY", "SELL"}:
        raise ValueError("The side must be BUY or SELL.")
    if tp_mode not in {"fixed_rr", "atr", "manual"}:
        raise ValueError("Take-profit mode must be fixed_rr, atr, or manual.")
    if tp_mode == "manual" and not body.get("tp_points"):
        raise ValueError("A manual take profit needs tp_points.")
    now = utcnow()
    signal = AdminSignal(
        id=uuid.uuid4(),
        symbol=str(body["symbol"]).upper()[:32],
        side=side,
        sl_points=int(body["sl_points"]),
        tp_mode=tp_mode,
        rr=None if body.get("rr") is None else Decimal(str(body["rr"])),
        tp_points=None if body.get("tp_points") is None else int(body["tp_points"]),
        note=_clean(str(body.get("note") or "")),
        created_by=admin.id,
        created_at=now,
    )
    db.add(signal)
    db.flush()
    recipients = _eligible_users(db)
    for user_id in recipients:
        db.add(
            UserSignal(
                id=uuid.uuid4(),
                signal_id=signal.id,
                user_id=user_id,
                status="pending",
                created_at=now,
                updated_at=now,
            )
        )
    return signal, len(recipients)


def _eligible_users(db: Session) -> list[uuid.UUID]:
    rows = (
        db.query(User.id)
        .join(BotConfig, BotConfig.user_id == User.id)
        .join(TradingAgent, TradingAgent.user_id == User.id)
        .filter(
            User.is_active.is_(True),
            BotConfig.status == "running",
            BotConfig.demo_trading_enabled.is_(True),
            TradingAgent.environment.in_(("demo", "live")),
            TradingAgent.mt5_connected.is_(True),
        )
        .all()
    )
    return [user_id for (user_id,) in rows if subscription_is_active(db, user_id)]


def expire_user_signals(db: Session, user_id: uuid.UUID) -> None:
    cutoff = utcnow() - timedelta(seconds=get_settings().signal_max_age_seconds)
    (
        db.query(UserSignal)
        .filter(
            UserSignal.user_id == user_id,
            UserSignal.status == "pending",
            UserSignal.created_at < cutoff,
        )
        .update({UserSignal.status: "expired", UserSignal.updated_at: utcnow()}, synchronize_session=False)
    )


def pending_signals_for_agent(db: Session, user_id: uuid.UUID) -> list[dict]:
    expire_user_signals(db, user_id)
    rows = (
        db.query(UserSignal, AdminSignal)
        .join(AdminSignal, AdminSignal.id == UserSignal.signal_id)
        .filter(UserSignal.user_id == user_id, UserSignal.status == "pending")
        .order_by(UserSignal.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(row.id),
            "signal_id": str(signal.id),
            "symbol": signal.symbol,
            "side": signal.side,
            "sl_points": signal.sl_points,
            "tp_mode": signal.tp_mode,
            "rr": None if signal.rr is None else float(signal.rr),
            "tp_points": signal.tp_points,
            "created_at": row.created_at,
        }
        for row, signal in rows
    ]


def acknowledge_signal(db: Session, user_id: uuid.UUID, user_signal_id: uuid.UUID, body: dict) -> dict:
    row = db.get(UserSignal, user_signal_id)
    if row is None or row.user_id != user_id:
        return {}
    if row.status != "pending":
        return _ack_view(row)
    cutoff = utcnow() - timedelta(seconds=get_settings().signal_max_age_seconds)
    if row.created_at < cutoff:
        row.status = "expired"
        row.updated_at = utcnow()
        return _ack_view(row)
    reasons = [_clean(str(item)) for item in (body.get("reasons") or []) if str(item).strip()]
    ticket = body.get("ticket")
    retcode = body.get("retcode")
    row.reasons = "; ".join(reasons)[:500] if reasons else None
    row.retcode = None if retcode is None else int(retcode)
    row.ticket = None if ticket is None else int(ticket)
    row.updated_at = utcnow()
    if row.retcode == 10009 and row.ticket is not None and row.ticket > 0 and not reasons:
        row.status = "sent"
    elif reasons:
        row.status = "blocked"
    else:
        row.status = "failed"
    return _ack_view(row)


def signal_counts(db: Session) -> list[dict]:
    signals = db.query(AdminSignal).order_by(AdminSignal.created_at.desc()).limit(20).all()
    views = []
    for signal in signals:
        rows = db.query(UserSignal).filter(UserSignal.signal_id == signal.id).all()
        counts = {"pending": 0, "sent": 0, "blocked": 0, "expired": 0, "failed": 0}
        for row in rows:
            if row.status in counts:
                counts[row.status] += 1
        views.append(
            {
                "id": signal.id,
                "symbol": signal.symbol,
                "side": signal.side,
                "tp_mode": signal.tp_mode,
                "created_at": signal.created_at,
                "recipients": len(rows),
                "counts": counts,
            }
        )
    return views


def _ack_view(row: UserSignal) -> dict:
    return {
        "id": str(row.id),
        "status": row.status,
        "retcode": row.retcode,
        "ticket": row.ticket,
        "reasons": row.reasons,
    }
