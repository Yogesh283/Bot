from __future__ import annotations

from decimal import Decimal

from mt5_agent.execution import ExecutionResult, OrderRequest


class MockGateway:
    def __init__(self) -> None:
        self.sent: list[OrderRequest] = []
        self.known: dict[str, ExecutionResult] = {}
        self.fail_send = False
        self.fail_lookup = False

    def find_by_comment(self, comment: str) -> ExecutionResult | None:
        if self.fail_lookup:
            raise RuntimeError("terminal lookup failed")
        return self.known.get(comment)

    def send_demo_order(self, request: OrderRequest) -> ExecutionResult:
        self.sent.append(request)
        if self.fail_send:
            raise RuntimeError("terminal disconnected during send")
        if request.volume <= Decimal("0"):
            return ExecutionResult("rejected", 10014, None, None, None, "Invalid volume.")
        result = ExecutionResult("filled", 10009, 88001, 88002, request.price, None)
        self.known[request.comment] = result
        return result
