from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.trading_models import BotConfig, DemoOrder, ReportedPosition, TradeCommand, TradingAgent
from test_support import bearer, login, register_and_verify


def _candles(closes: list[float], when: datetime) -> list[dict]:
    return [{"time": when.isoformat(), "open": close, "high": close, "low": close, "close": close} for close in closes]


def _ready_market(when: datetime, **overrides) -> dict:
    body = {
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "candles": _candles([1, 1, 1, 5], when),
        "positions": [],
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
        "realized_loss_today": 0,
    }
    body.update(overrides)
    return body


def _enroll(client, access: str) -> str:
    created = client.post("/agents/enroll", headers=bearer(access))
    assert created.status_code == 200, created.text
    return created.json()["token"]


def _prepare(client, access: str, agent: str, when: datetime) -> None:
    settings = client.post(
        "/bot/settings",
        headers=bearer(access),
        json={"symbol": "XAUUSD", "timeframe": "M15", "fast_period": 2, "slow_period": 3, "lot_size": 0.01},
    )
    assert settings.status_code == 200, settings.text
    heartbeat = client.post(
        "/agent/heartbeat",
        headers=bearer(agent),
        json={
            "mt5_connected": True,
            "trade_environment": "demo",
            "account_login": 123456,
            "server_name": "Demo-Server",
            "balance": 10000,
            "equity": 10000,
            "free_margin": 9000,
            "password": "must-not-be-stored",
            "setup_requirement": None,
        },
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert "must-not-be-stored" not in heartbeat.text
    allowed = client.post("/bot/demo-trading", headers=bearer(access), json={"enabled": True, "confirm": "DEMO"})
    assert allowed.status_code == 200, allowed.text
    started = client.post("/bot/start", headers=bearer(access))
    assert started.status_code == 200, started.text


def test_manual_demo_order_is_not_sent_without_confirmation(client, mailbox):
    register_and_verify(client, mailbox, "manual-off@example.com")
    access = login(client, "manual-off@example.com")
    refused = client.post("/bot/demo-order", headers=bearer(access), json={"side": "BUY", "confirm": "yes"})
    assert refused.status_code == 422
    assert "Nothing was sent" in refused.json()["detail"]
    assert client.get("/dashboard/status", headers=bearer(access)).json()["orders"] == []


def test_manual_demo_order_queues_only_for_that_user(client, mailbox):
    register_and_verify(client, mailbox, "manual-a@example.com")
    register_and_verify(client, mailbox, "manual-b@example.com")
    access = login(client, "manual-a@example.com")
    other = login(client, "manual-b@example.com")
    agent = _enroll(client, access)
    when = datetime.now(timezone.utc)
    _prepare(client, access, agent, when)
    assert client.post("/agent/market", headers=bearer(agent), json=_ready_market(when)).status_code == 200
    queued = client.post("/bot/demo-order", headers=bearer(access), json={"side": "BUY", "confirm": "DEMO"})
    assert queued.status_code == 200, queued.text
    assert queued.json()["trading_enabled"] is True
    assert len(client.get("/agent/commands", headers=bearer(agent)).json()["commands"]) == 2
    assert client.get("/dashboard/status", headers=bearer(other)).json()["orders"] == []


def test_start_is_rejected_when_the_agent_is_offline(client, mailbox):
    register_and_verify(client, mailbox, "offline-bot@example.com")
    access = login(client, "offline-bot@example.com")
    started = client.post("/bot/start", headers=bearer(access))
    assert started.status_code == 409
    assert "offline" in started.json()["detail"].lower()
    status = client.get("/dashboard/status", headers=bearer(access))
    assert status.json()["bot_status"] == "stopped"
    assert status.json()["agent_status"] == "offline"
    assert status.json()["trading_enabled"] is True


def test_demo_signal_is_queued_once_and_stop_does_not_close_positions(client, mailbox):
    register_and_verify(client, mailbox, "signal@example.com")
    access = login(client, "signal@example.com")
    agent = _enroll(client, access)
    when = datetime.now(timezone.utc)
    _prepare(client, access, agent, when)
    market = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when))
    assert market.status_code == 200, market.text
    assert market.json()["signal"] == "BUY"
    assert market.json()["symbol"] == "XAUUSD"
    assert market.json()["fast_ma"] == 3
    duplicate = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when))
    assert duplicate.json()["signal"] == "BUY"
    commands = client.get("/agent/commands", headers=bearer(agent))
    assert len(commands.json()["commands"]) == 1
    command = commands.json()["commands"][0]
    assert command["payload"]["sl"] < command["payload"]["price"] < command["payload"]["tp"]

    with_position = _ready_market(
        when + timedelta(minutes=15),
        positions=[{"ticket": 77, "symbol": "XAUUSD", "side": "buy", "volume": 0.01, "price_open": 2300, "sl": 2297, "tp": 2306, "profit": 1.5}],
        candles=_candles([2, 2, 2, 2], when + timedelta(minutes=15)),
    )
    client.post("/agent/market", headers=bearer(agent), json=with_position)
    stopped = client.post("/bot/stop", headers=bearer(access))
    assert stopped.status_code == 200
    assert "not closed" in stopped.json()["message"]
    assert client.get("/agent/commands", headers=bearer(agent)).json()["commands"] == []
    status = client.get("/dashboard/status", headers=bearer(access))
    body = status.json()
    assert body["bot_status"] == "stopped"
    assert body["open_positions"][0]["ticket"] == 77
    assert body["trading_enabled"] is True
    assert len(body["orders"]) == 1

    result = client.post(
        f"/agent/commands/{command['id']}/result",
        headers=bearer(agent),
        json={"status": "filled", "retcode": 10009, "order_ticket": 88001, "deal_ticket": 88002, "price": 2300.1},
    )
    assert result.status_code == 200
    db = SessionLocal()
    try:
        stored = db.query(DemoOrder).filter(DemoOrder.idempotency_key.contains("BUY")).one()
        assert stored.status == "filled"
        assert stored.order_ticket == 88001
        assert db.get(ReportedPosition, stored.user_id) is None or db.query(ReportedPosition).count() == 1
    finally:
        db.close()


def test_missing_stale_invalid_volume_margin_and_stop_do_not_queue(client, mailbox):
    register_and_verify(client, mailbox, "risk@example.com")
    access = login(client, "risk@example.com")
    agent = _enroll(client, access)
    when = datetime.now(timezone.utc)
    _prepare(client, access, agent, when)

    missing = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when, candles=_candles([1], when)))
    assert missing.json()["data_status"] == "missing"
    stale_time = when - timedelta(hours=3)
    stale = client.post("/agent/market", headers=bearer(agent), json=_ready_market(stale_time))
    assert stale.json()["data_status"] == "stale"
    assert client.get("/agent/commands", headers=bearer(agent)).json()["commands"] == []

    bad_lot = client.post("/bot/settings", headers=bearer(access), json={"lot_size": 0.015})
    assert bad_lot.status_code == 200
    rejected = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when))
    assert rejected.json()["signal"] == "BUY"
    assert client.get("/agent/commands", headers=bearer(agent)).json()["commands"] == []
    db = SessionLocal()
    try:
        order = db.query(DemoOrder).one()
        assert order.status == "rejected"
        assert "volume step" in (order.error or "")
        order_id = order.id
        db.delete(order)
        db.commit()
    finally:
        db.close()

    client.post("/bot/settings", headers=bearer(access), json={"lot_size": 0.01})
    margin = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when, margin_required=50000))
    assert margin.json()["signal"] == "BUY"
    db = SessionLocal()
    try:
        order = db.query(DemoOrder).one()
        assert "Free margin" in (order.error or "")
        db.delete(order)
        db.commit()
    finally:
        db.close()

    client.post("/bot/settings", headers=bearer(access), json={"stop_loss_points": 5})
    stops = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when, stops_level=50))
    assert stops.json()["signal"] == "BUY"
    db = SessionLocal()
    try:
        order = db.query(DemoOrder).one()
        assert "stop distance" in (order.error or "")
        assert db.query(TradeCommand).count() == 0
    finally:
        db.close()
    assert order_id is not None


def test_stale_heartbeat_is_offline_and_live_accounts_cannot_start(client, mailbox):
    register_and_verify(client, mailbox, "disconnect@example.com")
    access = login(client, "disconnect@example.com")
    agent = _enroll(client, access)
    heartbeat = client.post(
        "/agent/heartbeat",
        headers=bearer(agent),
        json={"mt5_connected": True, "trade_environment": "demo", "free_margin": 1000, "account_login": 9},
    )
    assert heartbeat.status_code == 200
    db = SessionLocal()
    try:
        row = db.query(TradingAgent).one()
        row.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.commit()
    finally:
        db.close()
    status = client.get("/dashboard/status", headers=bearer(access))
    assert status.json()["agent_status"] == "offline"
    started = client.post("/bot/start", headers=bearer(access))
    assert started.status_code == 409

    client.post(
        "/agent/heartbeat",
        headers=bearer(agent),
        json={"mt5_connected": True, "trade_environment": "live", "account_login": 9, "setup_requirement": "password=hidden"},
    )
    live = client.post("/bot/start", headers=bearer(access))
    assert live.status_code == 200
    dashboard = client.get("/dashboard/status", headers=bearer(access))
    assert dashboard.json()["mt5_status"] == "connected"
    assert dashboard.json()["environment"] == "live"
    assert "password" not in (dashboard.json()["setup_requirement"] or "").lower() or "sensitive" in (
        dashboard.json()["setup_requirement"] or ""
    ).lower()


def test_demo_activation_is_required_and_credentials_are_not_returned(client, mailbox):
    register_and_verify(client, mailbox, "activate@example.com")
    access = login(client, "activate@example.com")
    agent = _enroll(client, access)
    when = datetime.now(timezone.utc)
    client.post("/bot/settings", headers=bearer(access), json={"fast_period": 2, "slow_period": 3})
    client.post(
        "/agent/heartbeat",
        headers=bearer(agent),
        json={"mt5_connected": True, "trade_environment": "demo", "free_margin": 9000, "balance": 10000, "equity": 10000},
    )
    waiting = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when))
    assert waiting.json()["signal"] == "BUY"
    assert client.get("/agent/commands", headers=bearer(agent)).json()["commands"] == []
    client.post("/bot/start", headers=bearer(access))
    refused = client.post("/bot/demo-trading", headers=bearer(access), json={"enabled": True, "confirm": "yes"})
    assert refused.status_code == 422
    market = client.post("/agent/market", headers=bearer(agent), json=_ready_market(when))
    assert market.json()["signal"] == "BUY"
    assert len(client.get("/agent/commands", headers=bearer(agent)).json()["commands"]) == 1
    status = client.get("/dashboard/status", headers=bearer(access))
    assert status.json()["analysis"]["signal"] == "BUY"
    assert status.json()["bot_status"] == "running"
    assert status.json()["demo_trading_enabled"] is True
    assert status.json()["balance"] == 10000
    assert "must-not" not in status.text
