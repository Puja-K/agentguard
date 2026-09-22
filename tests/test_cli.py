"""Tests for the AgentGuard command-line foundation."""

from importlib.metadata import version

from typer.testing import CliRunner

from agentguard.cli import app

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
