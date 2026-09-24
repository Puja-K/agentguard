"""Static example agent used to demonstrate deterministic behavior extraction."""

from collections.abc import Callable


def tool[Function: Callable[..., object]](function: Function) -> Function:
    """Minimal local decorator that keeps the example executable."""
    return function


function_tool = tool


def process_refund(amount: float, currency: str) -> dict[str, object]:
    return {
        "status": "processed",
        "action": "process_refund",
        "amount": amount,
        "currency": currency,
    }


def escalate_to_human(amount: float, currency: str) -> dict[str, object]:
    return {"status": "human_review", "amount": amount, "currency": currency}


def find_payment(payment_id: str) -> dict[str, str]:
    return {"payment_id": payment_id, "status": "found"}


@tool
def issue_refund(amount: float, authenticated: bool, currency: str = "USD") -> object:
    """Issue a refund after identity and amount checks."""
    if not authenticated:
        raise PermissionError("authentication required")
    if amount <= 500:
        return process_refund(amount, currency)
    return escalate_to_human(amount, currency)


@function_tool
def lookup_payment(payment_id: str) -> object:
    """Look up a payment record."""
    if payment_id == "timeout":
        return {"error": "payment provider timed out"}
    return find_payment(payment_id)
