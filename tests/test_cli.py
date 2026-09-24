"""Tests for the AgentGuard command-line foundation."""

from importlib.metadata import version
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.models import (
    RepositoryMetadata,
    ScanCompleteness,
    ScanResult,
    ScanWarning,
    SkippedPath,
    SkipReason,
)

runner = CliRunner()


def test_help_succeeds() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Find potentially important AI-agent behaviors" in result.output
    assert "--version" in result.output


def test_bare_invocation_displays_help_and_succeeds() -> None:
    result = runner.invoke(app)

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--help" in result.output


def test_version_matches_installed_package_metadata() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == version("agentguard")


def test_unknown_command_is_a_usage_error() -> None:
    result = runner.invoke(app, ["unknown-command"])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_unknown_option_is_a_usage_error() -> None:
    result = runner.invoke(app, ["--unknown-option"])

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_scan_command_summarizes_valid_repository(tmp_path: Path) -> None:
    (tmp_path / "agent.py").write_text(
        "def test_answer():\n    assert answer() == 42\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert f"Repository: {tmp_path}" in result.output
    assert "Status: complete" in result.output
    assert "python" in result.output
    assert "total" in result.output
    assert "Discovered evals" in result.output
    assert "pytest" in result.output
    assert "Eval parse warnings: 0" in result.output
    assert "Detected behaviors" in result.output
    assert "Behavior extraction warnings: 0" in result.output
    assert "Coverage assessments" in result.output
    assert "Candidate pairs considered:" in result.output


def test_scan_command_rejects_nonexistent_repository(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing"

    result = runner.invoke(app, ["scan", str(missing_path)])

    assert result.exit_code != 0
    assert "Repository path does not exist" in result.output
    assert "Status: failed" in result.output


def test_scan_command_rejects_file_path(tmp_path: Path) -> None:
    file_path = tmp_path / "file.py"
    file_path.touch()

    result = runner.invoke(app, ["scan", str(file_path)])

    assert result.exit_code != 0
    assert "Repository path is not a directory" in result.output
    assert "Status: failed" in result.output


def test_scan_command_displays_warning_path_literally(monkeypatch: pytest.MonkeyPatch) -> None:
    scan_result = ScanResult(
        repository=RepositoryMetadata(requested_path="repository", root="/repository"),
        skipped=(SkippedPath(path="nested/link.py", reason=SkipReason.UNSUPPORTED),),
        warnings=(
            ScanWarning(
                code="symlink_unsupported",
                message="Symbolic links are not followed during repository discovery.",
                path="nested/link.py",
            ),
        ),
        completeness=ScanCompleteness.INCOMPLETE,
    )
    monkeypatch.setattr("agentguard.cli.scan_repository", lambda _: scan_result)

    result = runner.invoke(app, ["scan", "repository"])

    assert result.exit_code == 0
    assert "[nested/link.py]" in result.output
