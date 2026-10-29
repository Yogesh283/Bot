from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.security import as_utc, utcnow
from app.database import SessionLocal
from app.trading_models import BotConfig, Subscription, TradeCommand


class PaymentProvider(Protocol):
    def activate(self, db: Session, user_id: uuid.UUID, plan: str = "demo") -> Subscription:
        """Mark a plan active. Implementations must not log secrets or call a live broker."""


class FakeProvider:
    """Local stand-in. It stores no payment keys and does not contact a payment network."""

    def activate(self, db: Session, user_id: uuid.UUID, plan: str = "demo") -> Subscription:
        return grant_demo_subscription(db, user_id, plan=plan)


def grant_demo_subscription(db: Session, user_id: uuid.UUID, plan: str = "demo", days: int = 365) -> Subscription:
    now = utcnow()
    row = db.get(Subscription, user_id)
    if row is None:
        row = Subscription(
            user_id=user_id,
            plan=plan[:40],
            status="active",
            expires_at=now + timedelta(days=days),
            updated_at=now,
        )
        db.add(row)
    else:
        row.plan = plan[:40]
        row.status = "active"
        row.expires_at = now + timedelta(days=days)
        row.updated_at = now
    return row


def subscription_view(db: Session, user_id: uuid.UUID) -> dict:
    row = db.get(Subscription, user_id)
    if row is None:
        return {"plan": "none", "status": "none", "expires_at": None}
    status = row.status if row.status in {"active", "expired", "cancelled"} else "expired"
    plan_expires = as_utc(row.expires_at)
    if status == "active" and plan_expires is not None and plan_expires <= utcnow():
        status = "expired"
    return {"plan": row.plan, "status": status, "expires_at": row.expires_at}


def subscription_is_active(db: Session, user_id: uuid.UUID) -> bool:
    return subscription_view(db, user_id)["status"] == "active"


def enforce_subscriptions(db: Session | None = None) -> None:
    """Stop bots whose plan has expired. Commits on its own so a later 402 does not undo the stop."""
    now = utcnow()
    own = SessionLocal()
    try:
        rows = own.query(Subscription).filter(Subscription.status == "active", Subscription.expires_at <= now).all()
        for row in rows:
            row.status = "expired"
            row.updated_at = now
            config = own.get(BotConfig, row.user_id)
            if config is not None and config.status == "running":
                config.status = "stopped"
                config.updated_at = now
                (
                    own.query(TradeCommand)
                    .filter(TradeCommand.user_id == row.user_id, TradeCommand.status == "pending")
                    .update({TradeCommand.status: "cancelled"}, synchronize_session=False)
                )
        own.commit()
    finally:
        own.close()
    if db is not None:
        db.flush()
        db.expire_all()
