from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from mt5_agent.admin_signals import process_admin_signals
from mt5_agent.mock_gateway import MockGateway


class Api:
    def __init__(self, signals: list[dict]) -> None:
        self.signals = signals
        self.acks: list[dict] = []

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if method == "GET" and path == "/agent/signals":
            return {"signals": self.signals}
        if method == "POST" and path.endswith("/ack"):
            self.acks.append(payload or {})
            return {"saved": True}
        raise AssertionError(path)


class Market(MockGateway):
    def __init__(self, **overrides) -> None:
        super().__init__()
        self.snapshot = {
            "spread_points": 10,
            "bid": 2300,
            "ask": 2300.1,
            "point": 0.01,
            "min_volume": 0.01,
            "max_volume": 100,
            "volume_step": 0.01,
            "stops_level": 20,
            "symbol_trade_mode": "full",
            "margin_required": 50,
            "free_margin": 9000,
        }
        self.snapshot.update(overrides)
        self.candles = [{"high": 10, "low": 9, "close": 9.5}]
        for index in range(20):
            self.candles.append({"high": 11 + index, "low": 10 + index, "close": 10.5 + index})
        self.open_positions: list[dict] = []
        self.modified: list[tuple[int, float]] = []

    def symbol_snapshot(self, _symbol: str, _volume: Decimal) -> dict:
        return self.snapshot

    def completed_candles(self, _symbol: str, _timeframe: str) -> list[dict]:
        return self.candles

    def positions(self) -> list[dict]:
        return self.open_positions

    def realized_loss_today(self) -> float:
        return 0

    def modify_stop(self, ticket: int, sl: float) -> None:
        self.modified.append((ticket, sl))


def _instructions() -> dict:
    return {
        "bot_status": "running",
        "demo_trading_enabled": True,
        "lot_size": 0.01,
        "timeframe": "M15",
        "max_open_positions": 1,
        "max_spread_points": 50,
        "max_daily_loss": 100,
        "environment": "demo",
    }


def _signal(**overrides) -> dict:
    body = {
        "id": "user-signal-1",
        "signal_id": "admin-signal-1",
        "symbol": "XAUUSD",
        "side": "BUY",
        "sl_points": 300,
        "tp_mode": "fixed_rr",
        "rr": 2,
        "tp_points": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body.update(overrides)
    return body


def test_admin_signal_is_sent_once_with_fixed_risk_reward(tmp_path):
    market = Market()
    api = Api([_signal()])
    instructions = _instructions()
    ledger = tmp_path / "sent.json"
    process_admin_signals(api, market, market, instructions, sent_path=ledger)
    process_admin_signals(api, market, market, instructions, sent_path=ledger)
    assert len(market.sent) == 1
    order = market.sent[0]
    assert order.sl == 2297.1
    assert order.tp == 2306.1
    assert api.acks[0]["retcode"] == 10009
    assert api.acks[0]["ticket"] == 88001
    assert len(api.acks) == 1


def test_risk_block_and_expired_signal_do_not_send(tmp_path):
    wide = Market(spread_points=80)
    blocked = Api([_signal(id="user-signal-2", signal_id="admin-signal-2")])
    process_admin_signals(blocked, wide, wide, _instructions(), sent_path=tmp_path / "blocked.json")
    assert wide.sent == []
    assert blocked.acks[0]["ticket"] is None
    assert "spread" in blocked.acks[0]["reasons"][0].lower()

    old = _signal(
        id="user-signal-3",
        signal_id="admin-signal-3",
        created_at=(datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
    )
    expired = Api([old])
    market = Market()
    process_admin_signals(expired, market, market, _instructions(), sent_path=tmp_path / "expired.json")
    assert market.sent == []
    assert "older" in expired.acks[0]["reasons"][0]


def test_trailing_stop_moves_to_entry_after_one_r(tmp_path):
    market = Market()
    market.open_positions = [
        {"ticket": 7, "side": "BUY", "price_open": 100, "sl": 97, "price": 103},
    ]
    process_admin_signals(Api([]), market, market, _instructions(), sent_path=tmp_path / "trail.json")
    assert market.modified == [(7, 100.0)]
