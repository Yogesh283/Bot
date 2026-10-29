from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from mt5_agent.execution import ExecutionResult, OrderRequest, execute_once
from mt5_agent.mock_gateway import MockGateway
from mt5_agent.mt5_gateway import SETUP_ACCOUNT, SETUP_PACKAGE, SETUP_TERMINAL, TerminalGateway
from mt5_agent.runner import run_once


def _request() -> OrderRequest:
    return OrderRequest("XAUUSD", "BUY", Decimal("0.01"), 2297.0, 2306.0, 2300.1, "abc123")


def test_mock_order_is_sent_once_and_a_second_call_finds_the_ticket():
    gateway = MockGateway()
    first = execute_once(gateway, _request(), previous_status=None)
    second = execute_once(gateway, _request(), previous_status=None)
    assert first.status == "filled"
    assert first.retcode == 10009
    assert first.order_ticket == 88001
    assert second.status == "filled"
    assert second.error.startswith("The terminal already has this order")
    assert len(gateway.sent) == 1


def test_unknown_result_is_not_retried_and_lookup_failure_does_not_send():
    gateway = MockGateway()
    gateway.fail_send = True
    unknown = execute_once(gateway, _request(), previous_status=None)
    assert unknown.status == "unknown"
    gateway.fail_send = False
    held = execute_once(gateway, _request(), previous_status="unknown")
    assert held.status == "unknown"
    assert len(gateway.sent) == 1

    lookup = MockGateway()
    lookup.fail_lookup = True
    blocked = execute_once(lookup, _request(), previous_status=None)
    assert blocked.status == "unknown"
    assert lookup.sent == []


def test_disconnected_terminal_reports_setup_and_does_not_send(monkeypatch):
    monkeypatch.setattr("mt5_agent.mt5_gateway._import_mt5", lambda: None)
    status = TerminalGateway().connect()
    assert status.connected is False
    assert status.setup_requirement == SETUP_PACKAGE

    class MissingTerminal:
        def initialize(self):
            return False

        def last_error(self):
            return (1, "terminal closed")

        def order_send(self, *_args, **_kwargs):
            raise AssertionError("order_send was called")

    monkeypatch.setattr("mt5_agent.mt5_gateway._import_mt5", lambda: MissingTerminal())
    failed = TerminalGateway().connect()
    assert SETUP_TERMINAL in (failed.setup_requirement or "")

    class NoAccount:
        def initialize(self):
            return True

        def account_info(self):
            return None

        def order_send(self, *_args, **_kwargs):
            raise AssertionError("order_send was called")

    monkeypatch.setattr("mt5_agent.mt5_gateway._import_mt5", lambda: NoAccount())
    empty = TerminalGateway().connect()
    assert empty.setup_requirement == SETUP_ACCOUNT


def test_live_terminal_is_rejected_without_sending(monkeypatch):
    class LiveTerminal:
        ACCOUNT_TRADE_MODE_REAL = 0
        ACCOUNT_TRADE_MODE_DEMO = 1

        def initialize(self):
            return True

        def account_info(self):
            return SimpleNamespace(trade_mode=0, login=100, server="Live-Server", balance=1, equity=1, margin_free=1)

        def order_send(self, *_args, **_kwargs):
            raise AssertionError("order_send was called")

    monkeypatch.setattr("mt5_agent.mt5_gateway._import_mt5", lambda: LiveTerminal())
    status = TerminalGateway().connect()
    assert status.connected is True
    assert status.environment == "live"


class _Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        self.calls.append((method, path))
        return {}


def test_agent_cycle_stops_before_market_data_when_mt5_is_offline():
    class Offline:
        def connect(self):
            from mt5_agent.mt5_gateway import TerminalStatus

            return TerminalStatus(False, "unknown", SETUP_PACKAGE)

        def send_demo_order(self, _request: OrderRequest) -> ExecutionResult:
            raise AssertionError("order was sent while disconnected")

    client = _Client()
    run_once(client, Offline())
    assert client.calls == [("POST", "/agent/heartbeat")]
