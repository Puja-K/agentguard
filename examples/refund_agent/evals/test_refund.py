"""Representative pytest-style evals; AgentGuard parses but does not execute this file."""

import pytest

from examples.refund_agent.agent import issue_refund


def test_small_refund_is_processed() -> None:
    result = issue_refund(25, authenticated=True)
    assert isinstance(result, dict)
    assert result["status"] == "processed"
    assert result["action"] == "process_refund"


def test_unauthenticated_refund_is_rejected() -> None:
    with pytest.raises(PermissionError):
        issue_refund(25, authenticated=False)
