"""Accuracy from closed trades only. An open trade is not a result, and profit is not predicted."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.trading_models import TradeSample


def accuracy_view(db: Session, user_id) -> dict:
    closed = (
        db.query(TradeSample)
        .filter(TradeSample.user_id == user_id, TradeSample.status == "closed", TradeSample.profit.is_not(None))
        .all()
    )
    wins = sum(1 for row in closed if row.profit is not None and row.profit > 0)
    return {
        "closed_trades": len(closed),
        "wins": wins,
        "accuracy": None if not closed else round(wins / len(closed), 4),
    }
