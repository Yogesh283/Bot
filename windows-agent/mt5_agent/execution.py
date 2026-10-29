from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    volume: Decimal
    sl: float
    tp: float
    price: float
    comment: str


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    retcode: int | None
    order_ticket: int | None
    deal_ticket: int | None
    price: float | None
    error: str | None


class BrokerGateway(Protocol):
    def find_by_comment(self, comment: str) -> ExecutionResult | None: ...

    def send_demo_order(self, request: OrderRequest) -> ExecutionResult: ...


def execute_once(
    gateway: BrokerGateway,
    request: OrderRequest,
    *,
    previous_status: str | None,
) -> ExecutionResult:
    """Send at most one new order. An unknown earlier result is never blindly retried."""
    try:
        existing = gateway.find_by_comment(request.comment)
    except Exception as exc:
        return ExecutionResult("unknown", None, None, None, None, f"Could not check the terminal before sending: {exc}")
    if existing is not None and (existing.order_ticket or existing.deal_ticket):
        return ExecutionResult(
            "filled",
            existing.retcode,
            existing.order_ticket,
            existing.deal_ticket,
            existing.price,
            "The terminal already has this order. It was not sent again.",
        )
    if previous_status == "unknown":
        return ExecutionResult(
            "unknown",
            None,
            None,
            None,
            None,
            "Not sent again because the previous result was unknown and the terminal did not show the order.",
        )
    try:
        result = gateway.send_demo_order(request)
    except Exception as exc:
        return ExecutionResult("unknown", None, None, None, None, f"The terminal did not return a result: {exc}")
    if result.status == "filled" and result.retcode is not None and (result.order_ticket or result.deal_ticket):
        return result
    if result.status == "rejected":
        return result
    return ExecutionResult(
        "unknown",
        result.retcode,
        result.order_ticket,
        result.deal_ticket,
        result.price,
        result.error or "The terminal result had no confirmed ticket.",
    )
