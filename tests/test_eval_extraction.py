"""Tests for static pytest and JSONL eval extraction."""

from pathlib import Path

import pytest

from agentguard.extractors import parse_eval_artifacts
from agentguard.models import (
    EvalAssertionKind,
    EvalParseResult,
    EvalSourceType,
    ScanCompleteness,
)
from agentguard.scanners import scan_repository


def write_file(root: Path, relative_path: str, contents: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def parse_repository(root: Path) -> EvalParseResult:
    return parse_eval_artifacts(scan_repository(root))


def test_plain_pytest_function_retains_symbol_assert_and_evidence(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "tests/test_refund.py",
        '''def test_refund_succeeds(refund_client):
    """Refunds a valid payment."""
    result = issue_refund("payment-1", amount=25, dry_run=False)
    assert result.status == "completed"
''',
    )

    result = parse_repository(tmp_path)

    assert result.completeness is ScanCompleteness.COMPLETE
    assert len(result.scenarios) == 1
    scenario = result.scenarios[0]
    assert scenario.source_type is EvalSourceType.PYTEST
    assert scenario.source_file == "tests/test_refund.py"
    assert scenario.source_symbol == "test_refund_succeeds"
    assert scenario.description == "Refunds a valid payment."
    assert scenario.inputs == {"parameters": ["refund_client"]}
    assert scenario.assertions[0].kind is EvalAssertionKind.ASSERT
    assert scenario.assertions[0].expression == "result.status == 'completed'"
    assert scenario.evidence[0].excerpt.startswith("def test_refund_succeeds")
    refund_reference = next(
        reference
        for reference in scenario.referenced_symbols
        if reference.qualified_name == "issue_refund"
    )
    assert [argument.value for argument in refund_reference.literal_arguments] == [
        "payment-1",
        25,
        False,
    ]


def test_pytest_method_and_multiple_asserts_are_discovered(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "refund_test.py",
        """class TestRefunds:
    def test_result(self):
        result = refund()
        assert result.ok
        assert result.amount == 10
""",
    )

    scenario = parse_repository(tmp_path).scenarios[0]

    assert scenario.source_symbol == "TestRefunds.test_result"
    assert len(scenario.assertions) == 2
    assert scenario.expected_outcome is not None
    assert "result.ok" in scenario.expected_outcome.description
    assert "result.amount == 10" in scenario.expected_outcome.description


def test_expected_exception_context_and_function_patterns(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "tests/test_errors.py",
        """def test_context_error():
    with pytest.raises(TimeoutError, match="slow"):
        fetch_payment()

def test_function_error():
    pytest.raises(ValueError, parse_payment, "bad")
""",
    )

    scenarios = parse_repository(tmp_path).scenarios

    assert [scenario.assertions[0].expected_exception for scenario in scenarios] == [
        "TimeoutError",
        "ValueError",
    ]
    assert all(
        scenario.assertions[0].kind is EvalAssertionKind.EXPECTED_EXCEPTION
        for scenario in scenarios
    )


def test_eval_id_is_stable_across_formatting_and_line_movement(tmp_path: Path) -> None:
    path = write_file(
        tmp_path,
        "tests/test_agent.py",
        """def test_answer():
    value=answer(  42 )
    assert value=="yes"
""",
    )
    first = parse_repository(tmp_path).scenarios[0]
    path.write_text(
        """# unrelated line


def test_answer():
    value = answer(42)
    assert value == "yes"
""",
        encoding="utf-8",
    )

    second = parse_repository(tmp_path).scenarios[0]

    assert second.eval_id == first.eval_id
    assert second.content_fingerprint == first.content_fingerprint


def test_meaningful_test_change_changes_fingerprint_not_identity(tmp_path: Path) -> None:
    path = write_file(
        tmp_path,
        "tests/test_agent.py",
        'def test_answer():\n    assert answer() == "yes"\n',
    )
    first = parse_repository(tmp_path).scenarios[0]
    path.write_text('def test_answer():\n    assert answer() == "no"\n', encoding="utf-8")

    second = parse_repository(tmp_path).scenarios[0]

    assert second.eval_id == first.eval_id
    assert second.content_fingerprint != first.content_fingerprint


def test_jsonl_input_and_expected_are_parsed(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "evals/cases.jsonl",
        '{"input":"refund payment","expected":"refund completed"}\n',
    )

    scenario = parse_repository(tmp_path).scenarios[0]

    assert scenario.source_type is EvalSourceType.JSONL
    assert scenario.inputs == "refund payment"
    assert scenario.expected_outcome is not None
    assert scenario.expected_outcome.value == "refund completed"


def test_jsonl_without_expected_has_no_expected_outcome(tmp_path: Path) -> None:
    write_file(tmp_path, "cases.jsonl", '{"input":"describe account"}\n')

    scenario = parse_repository(tmp_path).scenarios[0]

    assert scenario.expected_outcome is None


def test_jsonl_line_movement_preserves_id_and_content_change_updates_fingerprint(
    tmp_path: Path,
) -> None:
    path = write_file(tmp_path, "cases.jsonl", '{"input":"refund","expected":"accepted"}\n')
    first = parse_repository(tmp_path).scenarios[0]
    path.write_text('\n\n{"input":"refund","expected":"rejected"}\n', encoding="utf-8")

    second = parse_repository(tmp_path).scenarios[0]

    assert second.eval_id == first.eval_id
    assert second.content_fingerprint != first.content_fingerprint


def test_jsonl_metadata_tools_and_unknown_fields_are_preserved(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "cases.jsonl",
        """{"input":"refund","metadata":{"name":"refund_case","tools":["refund_tool"],"owner":"qa"},"priority":"high"}
""",
    )

    scenario = parse_repository(tmp_path).scenarios[0]

    assert scenario.name == "refund_case"
    assert scenario.source_symbol == "refund_case"
    assert scenario.metadata["owner"] == "qa"
    assert scenario.unknown_fields == {"priority": "high"}
    assert scenario.referenced_symbols[0].qualified_name == "refund_tool"


def test_malformed_jsonl_line_warns_while_valid_records_continue(tmp_path: Path) -> None:
    write_file(
        tmp_path,
        "cases.jsonl",
        '{"input":"first"}\nnot json\n{"input":"second","expected":"ok"}\n',
    )

    result = parse_repository(tmp_path)

    assert result.completeness is ScanCompleteness.INCOMPLETE
    assert [scenario.inputs for scenario in result.scenarios] == ["first", "second"]
    assert result.warnings[0].code == "jsonl_malformed"
    assert result.warnings[0].line == 2


def test_invalid_test_python_does_not_discard_other_evals(tmp_path: Path) -> None:
    write_file(tmp_path, "tests/test_broken.py", "def test_broken(:\n")
    write_file(tmp_path, "tests/test_valid.py", "def test_valid():\n    assert run()\n")

    result = parse_repository(tmp_path)

    assert result.completeness is ScanCompleteness.INCOMPLETE
    assert [scenario.name for scenario in result.scenarios] == ["test_valid"]
    assert result.warnings[0].code == "python_syntax_error"


def test_invalid_ordinary_python_is_not_classified_as_eval(tmp_path: Path) -> None:
    write_file(tmp_path, "src/broken.py", "def broken(:\n")
    write_file(tmp_path, "src/ordinary.py", "def helper():\n    return True\n")

    result = parse_repository(tmp_path)

    assert result.completeness is ScanCompleteness.COMPLETE
    assert result.scenarios == ()
    assert result.warnings == ()


def test_nonconventional_file_with_test_function_is_discovered(tmp_path: Path) -> None:
    write_file(tmp_path, "checks.py", "def test_static_discovery():\n    assert check()\n")

    assert parse_repository(tmp_path).scenarios[0].name == "test_static_discovery"


def test_target_python_is_never_imported_or_executed(tmp_path: Path) -> None:
    sentinel = tmp_path / "executed"
    write_file(
        tmp_path,
        "tests/test_dangerous.py",
        f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n\n"
        "def test_safe():\n    assert True\n",
    )

    result = parse_repository(tmp_path)

    assert len(result.scenarios) == 1
    assert not sentinel.exists()
    assert not (tmp_path / ".agentguard").exists()


def test_output_order_is_deterministic(tmp_path: Path) -> None:
    write_file(tmp_path, "tests/test_z.py", "def test_z():\n    assert z()\n")
    write_file(tmp_path, "tests/test_a.py", "def test_a():\n    assert a()\n")
    write_file(tmp_path, "cases.jsonl", '{"input":"b"}\n{"input":"a"}\n')

    first = parse_repository(tmp_path)
    second = parse_repository(tmp_path)

    assert first == second
    assert [
        (scenario.source_file, scenario.source_symbol or "") for scenario in first.scenarios
    ] == sorted(
        (scenario.source_file, scenario.source_symbol or "") for scenario in first.scenarios
    )


@pytest.mark.parametrize("wrapper", ["invoke", "ainvoke", "coroutine"])
def test_known_tool_wrapper_call_preserves_raw_and_normalizes_identity(
    tmp_path: Path, wrapper: str
) -> None:
    write_file(tmp_path, "agent.py", "@tool\ndef lookup(key):\n    return key\n")
    write_file(
        tmp_path,
        "tests/test_agent.py",
        f"def test_lookup():\n    result = lookup.{wrapper}({{'key': 'a'}})\n    assert result\n",
    )

    scenario = parse_repository(tmp_path).scenarios[0]
    reference = next(
        item for item in scenario.referenced_symbols if item.qualified_name == f"lookup.{wrapper}"
    )

    assert reference.name == wrapper
    assert reference.normalized_tool_name == "lookup"


def test_unrelated_object_wrapper_is_not_normalized(tmp_path: Path) -> None:
    write_file(tmp_path, "agent.py", "@tool\ndef lookup(key):\n    return key\n")
    write_file(
        tmp_path,
        "tests/test_agent.py",
        "def test_client():\n"
        "    result = unrelated_object.ainvoke({'key': 'a'})\n"
        "    assert result\n",
    )

    reference = next(
        item
        for item in parse_repository(tmp_path).scenarios[0].referenced_symbols
        if item.qualified_name == "unrelated_object.ainvoke"
    )

    assert reference.normalized_tool_name is None


def test_similarly_named_non_tool_wrapper_is_not_normalized(tmp_path: Path) -> None:
    write_file(tmp_path, "agent.py", "@tool\ndef lookup(key):\n    return key\n")
    write_file(
        tmp_path,
        "tests/test_agent.py",
        "def test_client():\n    result = lookup_client.ainvoke({'key': 'a'})\n    assert result\n",
    )

    reference = next(
        item
        for item in parse_repository(tmp_path).scenarios[0].referenced_symbols
        if item.qualified_name == "lookup_client.ainvoke"
    )

    assert reference.normalized_tool_name is None
