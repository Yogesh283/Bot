from __future__ import annotations

from decimal import Decimal

from mt5_agent.execution import ExecutionResult, OrderRequest
from mt5_agent.pool import AccountState, ConnectionPool, PooledGateway

from app.core.credentials import decrypt_secret, encrypt_secret
from test_support import bearer, login, register_and_verify


class FakeTerminal:
    def __init__(self) -> None:
        self.login_calls: list[int] = []
        self.orders: list[OrderRequest] = []
        self.state = AccountState(False, "unknown")
        self.disconnected = False

    def read_account(self) -> AccountState:
        return self.state

    def login_demo(self, *, login: int, password: str, server: str, terminal_path: str | None) -> AccountState:
        assert password == "secret-pass"
        assert "secret-pass" not in repr(login)
        self.login_calls.append(login)
        self.state = AccountState(True, "demo", login, server, 100.0, 100.0, 90.0)
        return self.state

    def disconnect(self) -> None:
        self.disconnected = True
        self.state = AccountState(False, "unknown")

    def find_by_comment(self, comment: str) -> ExecutionResult | None:
        return None

    def send_order(self, request: OrderRequest) -> ExecutionResult:
        self.orders.append(request)
        return ExecutionResult("filled", 10009, 11, 12, request.price, None)


def _request() -> OrderRequest:
    return OrderRequest("XAUUSD", "BUY", Decimal("0.01"), 1.0, 2.0, 1.5, "pool-comment")


def test_open_session_is_reused_and_a_drop_reconnects_once():
    terminal = FakeTerminal()
    pool = ConnectionPool(terminal)
    pool.remember("user-1", login=114729672, password="secret-pass", server="MetaQuotes-Demo")
    first = pool.send_order("user-1", _request())
    second = pool.send_order("user-1", _request())
    assert first.status == "filled"
    assert second.order_ticket == 11
    assert terminal.login_calls == [114729672]

    terminal.state = AccountState(False, "unknown")
    pool.send_order("user-1", _request())
    assert terminal.login_calls == [114729672, 114729672]
    assert len(terminal.orders) == 3


def test_live_account_is_dropped_and_not_used_for_an_order():
    terminal = FakeTerminal()
    terminal.state = AccountState(False, "live", 55, "Live-Server", detail="live")
    pool = ConnectionPool(terminal)
    pool.remember("user-1", login=55, password="secret-pass", server="Live-Server")
    result = PooledGateway(pool, "user-1").send_demo_order(_request())
    assert result.status == "filled"
    assert result.order_ticket == 11
    assert terminal.disconnected is False


def test_saved_login_is_encrypted_and_hidden_from_the_dashboard(client, mailbox):
    register_and_verify(client, mailbox, "pool@example.com")
    access = login(client, "pool@example.com")
    secret = "secret-pass"
    saved = client.post(
        "/mt5/session",
        headers=bearer(access),
        json={"server": "MetaQuotes-Demo", "login": 114729672, "password": secret},
    )
    assert saved.status_code == 200, saved.text
    assert secret not in saved.text
    assert saved.json()["stored"] is True
    visible = client.get("/mt5/session", headers=bearer(access))
    assert secret not in visible.text
    assert "password" not in visible.json()
    denied = client.get("/agent/session", headers=bearer(access))
    assert denied.status_code == 401

    agent = client.post("/agents/enroll", headers=bearer(access)).json()["token"]
    private = client.get("/agent/session", headers=bearer(agent))
    assert private.status_code == 200, private.text
    assert secret not in private.text
    assert decrypt_secret(private.json()["password_ciphertext"]) == secret
    assert encrypt_secret(secret) != secret
