"""Tests for deterministic static behavior extraction."""

from pathlib import Path

from agentguard.extractors.behaviors import extract_behaviors
from agentguard.models import Behavior, BehaviorType, ScanCompleteness
from agentguard.scanners import scan_repository


def _extract(root: Path) -> tuple[Behavior, ...]:
    return extract_behaviors(scan_repository(root)).behaviors


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_decorated_tool_produces_invocation_with_required_arguments(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.py",
        """
@tool
def search(query: str, limit: int = 10, *, locale: str):
    return run_search(query, limit, locale)
""",
    )

    behaviors = _extract(tmp_path)

    invocation = next(
        item for item in behaviors if item.behavior_type is BehaviorType.TOOL_INVOCATION
    )
    assert invocation.source_symbol == "search"
    assert [(item.name, item.required) for item in invocation.arguments] == [
        ("query", True),
        ("limit", False),
        ("locale", True),
    ]
    assert invocation.evidence[0].kind == "tool_definition"
    assert invocation.confidence.value == "high"


def test_literal_tool_registration_is_recognized(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.py",
        """
def search(query):
    return query

model = llm.bind_tools([search])
""",
    )

    assert [item.subject for item in _extract(tmp_path)] == ["search"]


def test_explicit_raise_records_failure_condition(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.py",
        """
@tool
def refund(authenticated):
    if not authenticated:
        raise PermissionError("authentication required")
    return process_refund()
""",
    )

    failures = [
        item for item in _extract(tmp_path) if item.behavior_type is BehaviorType.TOOL_FAILURE
    ]

    assert len(failures) == 1
    assert failures[0].condition is not None
    assert "not authenticated" in failures[0].condition.expression
    assert failures[0].action is not None
    assert failures[0].action.outcome == "PermissionError"


def test_multiple_explicit_failure_modes_are_separate_behaviors(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.py",
        """
@tool
def charge(card, amount):
    if not card:
        raise ValueError("missing card")
    if amount < 0:
        return {"error": "invalid amount"}
    if amount == 0:
        return False
    return {"success": True}
""",
    )

    failures = [
        item for item in _extract(tmp_path) if item.behavior_type is BehaviorType.TOOL_FAILURE
    ]

    assert len(failures) == 3
    assert len({item.behavior_id for item in failures}) == 3


def test_conditional_return_produces_branch_behavior(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.py",
        """
@tool
def refund(amount):
    if amount <= 500:
        return process_automatically(amount)
    return escalate_to_human(amount)
""",
    )

    branches = [
        item for item in _extract(tmp_path) if item.behavior_type is BehaviorType.CONDITIONAL_BRANCH
    ]

    assert len(branches) == 1
    assert branches[0].action is not None
    assert branches[0].action.target == "process_automatically"


def test_langgraph_edges_produce_transition_branch_fallback_and_escalation(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "workflow.py",
        """
graph = StateGraph(dict)
graph.add_edge("lookup", "refund")
graph.add_conditional_edges(
    "refund",
    route_refund,
    {"automatic": "process", "review": "human_review", "fallback": "fallback"},
)
""",
    )

    behaviors = _extract(tmp_path)

    assert {item.behavior_type for item in behaviors} == {
        BehaviorType.WORKFLOW_TRANSITION,
        BehaviorType.CONDITIONAL_BRANCH,
        BehaviorType.ESCALATION,
        BehaviorType.FALLBACK,
    }
    assert {item.action.target for item in behaviors if item.action} == {
        "refund",
        "process",
        "human_review",
        "fallback",
    }


def test_tool_escalation_and_handoff_calls_are_detected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "agent.py",
        """
@tool
def route(risky):
    if risky:
        return handoff_to_human()
    escalate_case()
""",
    )

    escalations = [
        item for item in _extract(tmp_path) if item.behavior_type is BehaviorType.ESCALATION
    ]

    assert {item.action.target for item in escalations if item.action} == {
        "handoff_to_human",
        "escalate_case",
    }


def test_ordinary_helpers_and_ambiguous_registration_are_not_behaviors(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "helpers.py",
        """
def helper(value):
    if value:
        return do_work(value)
    return None

dynamic_tools = build_tools(helper)
model.bind_tools(dynamic_tools)
""",
    )

    assert _extract(tmp_path) == ()


def test_prompt_candidates_do_not_create_natural_language_behaviors(tmp_path: Path) -> None:
    _write(tmp_path, "prompts/system.txt", "Always verify identity before issuing a refund.")

    assert _extract(tmp_path) == ()


def test_behavior_id_is_stable_across_whitespace_and_line_movement(tmp_path: Path) -> None:
    path = tmp_path / "agent.py"
    path.write_text("@tool\ndef search(query):\n    return lookup(query)\n", encoding="utf-8")
    before = _extract(tmp_path)[0]
    path.write_text(
        "\n\n@tool\ndef search( query ):\n\n    return lookup( query )\n",
        encoding="utf-8",
    )
    after = _extract(tmp_path)[0]

    assert after.behavior_id == before.behavior_id
    assert after.content_fingerprint == before.content_fingerprint
    assert after.evidence[0].start_line != before.evidence[0].start_line


def test_material_tool_body_change_updates_fingerprint_but_not_invocation_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agent.py"
    path.write_text("@tool\ndef search(query):\n    return lookup(query)\n", encoding="utf-8")
    before = _extract(tmp_path)[0]
    path.write_text(
        "@tool\ndef search(query):\n    return lookup_cached(query)\n", encoding="utf-8"
    )
    after = _extract(tmp_path)[0]

    assert after.behavior_id == before.behavior_id
    assert after.content_fingerprint != before.content_fingerprint


def test_invalid_python_marks_extraction_incomplete_and_keeps_valid_behaviors(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "broken.py", "def broken(:\n")
    _write(tmp_path, "valid.py", "@tool\ndef search(query):\n    return query\n")

    result = extract_behaviors(scan_repository(tmp_path))

    assert result.completeness is ScanCompleteness.INCOMPLETE
    assert len(result.behaviors) == 1
    assert result.warnings[0].code == "behavior_python_syntax_error"
    assert result.warnings[0].source_file == "broken.py"


def test_target_python_is_never_executed(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed.txt"
    _write(
        tmp_path,
        "agent.py",
        f"""
from pathlib import Path
Path({str(sentinel)!r}).write_text("executed")

@tool
def search(query):
    return query
""",
    )

    assert len(_extract(tmp_path)) == 1
    assert not sentinel.exists()


def test_behavior_order_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path, "z.py", "@tool\ndef zed(value):\n    return value\n")
    _write(tmp_path, "a.py", "@tool\ndef alpha(value):\n    return value\n")

    first = _extract(tmp_path)
    second = _extract(tmp_path)
    keys = [(item.source_file, item.source_symbol, item.behavior_type.value) for item in first]

    assert first == second
    assert keys == sorted(keys)


def test_behavior_extraction_creates_no_local_state(tmp_path: Path) -> None:
    _write(tmp_path, "agent.py", "@tool\ndef search(query):\n    return query\n")

    _extract(tmp_path)

    assert not (tmp_path / ".agentguard").exists()
