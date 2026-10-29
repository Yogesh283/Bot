from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.core.security import utcnow

from strategy_engine.alarm import raise_alarm
from strategy_engine.moving_average import MovingAverageConfig

from app.database import SessionLocal
from app.models import User
from app.trading_models import TradeSample
from test_support import bearer, login, register_and_verify


def test_alarm_trades_only_when_the_completed_cross_and_close_agree():
    when = datetime.now(timezone.utc)
    config = MovingAverageConfig(2, 3)
    confirmed = raise_alarm([1, 1, 1, 5], when, config, timeframe="M15", now=when)
    assert confirmed.side == "BUY"
    flat = raise_alarm([5, 5, 5, 5], when, config, timeframe="M15", now=when)
    assert flat.side is None


def test_accuracy_counts_closed_trades_only(client, mailbox):
    register_and_verify(client, mailbox, "accuracy@example.com")
    access = login(client, "accuracy@example.com")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "accuracy@example.com").one()
        db.add_all(
            [
                TradeSample(user_id=user.id, order_ticket=1, symbol="XAUUSD", side="BUY", volume=Decimal("0.01"), profit=Decimal("2"), status="closed", opened_at=utcnow()),
                TradeSample(user_id=user.id, order_ticket=2, symbol="XAUUSD", side="SELL", volume=Decimal("0.01"), profit=Decimal("-2"), status="closed", opened_at=utcnow()),
                TradeSample(user_id=user.id, order_ticket=3, symbol="XAUUSD", side="SELL", volume=Decimal("0.01"), profit=Decimal("-1"), status="open", opened_at=utcnow()),
            ]
        )
        db.commit()
    finally:
        db.close()
    body = client.get("/dashboard/status", headers=bearer(access)).json()
    assert body["accuracy"]["closed_trades"] == 2
    assert body["accuracy"]["wins"] == 1
    assert body["accuracy"]["accuracy"] == 0.5
    assert body["trading_enabled"] is True
