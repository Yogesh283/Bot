from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.services.control_auth import create_control_admin
from app.trading_models import TradeCommand
from test_support import PASSWORD, bearer, login, register_and_verify


def _connect(client, access: str, login_id: int) -> str:
    agent = client.post("/agents/enroll", headers=bearer(access)).json()["token"]
    assert (
        client.post(
            "/agent/heartbeat",
            headers=bearer(agent),
            json={
                "mt5_connected": True,
                "trade_environment": "demo",
                "account_login": login_id,
                "server_name": "Demo-Server",
                "balance": 10000,
                "equity": 10000,
                "free_margin": 9000,
            },
        ).status_code
        == 200
    )
    when = datetime.now(timezone.utc).isoformat()
    market = client.post(
        "/agent/market",
        headers=bearer(agent),
        json={
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "candles": [{"time": when, "open": 1, "high": 1, "low": 1, "close": 1}],
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
        },
    )
    assert market.status_code == 200, market.text
    return agent


def test_admin_panel_login_is_separate_and_copies_one_trade(client, mailbox):
    register_and_verify(client, mailbox, "copy-a@example.com")
    register_and_verify(client, mailbox, "copy-b@example.com")
    register_and_verify(client, mailbox, "copy-off@example.com")
    access_a = login(client, "copy-a@example.com")
    access_b = login(client, "copy-b@example.com")
    access_off = login(client, "copy-off@example.com")
    agent_a = _connect(client, access_a, 101)
    agent_b = _connect(client, access_b, 202)
    client.post("/agents/enroll", headers=bearer(access_off))

    db = SessionLocal()
    try:
        create_control_admin(db, "desk", PASSWORD)
        db.commit()
    finally:
        db.close()

    denied = client.post("/control/login", json={"username": "desk", "password": "wrong-password-1"})
    assert denied.status_code == 401
    signed = client.post("/control/login", json={"username": "desk", "password": PASSWORD})
    assert signed.status_code == 200, signed.text
    token = signed.json()["access_token"]
    assert client.get("/dashboard/status", headers=bearer(token)).status_code == 401
    assert client.post("/control/trades", headers=bearer(access_a), json={"symbol": "XAUUSD", "side": "SELL", "lot": 0.02}).status_code == 401
    user_login = client.post("/auth/login", json={"email": "desk", "password": PASSWORD})
    assert user_login.status_code in {401, 422}
    assert "access_token" not in user_login.text

    copied = client.post(
        "/control/trades",
        headers=bearer(token),
        json={"symbol": "xauusd", "side": "SELL", "lot": 0.02},
    )
    assert copied.status_code == 200, copied.text
    body = copied.json()
    assert body["queued"] == 2
    assert body["symbol"] == "XAUUSD"
    assert body["side"] == "SELL"
    assert body["lot"] == 0.02
    assert PASSWORD not in copied.text

    for agent in (agent_a, agent_b):
        commands = client.get("/agent/commands", headers=bearer(agent)).json()["commands"]
        assert len(commands) == 1
        assert commands[0]["payload"]["symbol"] == "XAUUSD"
        assert commands[0]["payload"]["side"] == "SELL"
        assert Decimal(commands[0]["payload"]["volume"]) == Decimal("0.02")

    db = SessionLocal()
    try:
        assert db.query(TradeCommand).count() == 2
    finally:
        db.close()
