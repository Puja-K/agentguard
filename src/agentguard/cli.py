"""Command-line interface for AgentGuard."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from agentguard.models import ArtifactType, ScanCompleteness, ScanResult
from agentguard.scanners import scan_repository

PACKAGE_NAME = "agentguard"

app = typer.Typer(
    help="Find potentially important AI-agent behaviors that lack adequate eval coverage.",
    invoke_without_command=True,
    no_args_is_help=False,
)
console = Console()
error_console = Console(stderr=True)


def get_version() -> str:
    """Return the version from the installed package metadata."""
    return version(PACKAGE_NAME)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(get_version())
        raise typer.Exit()


def _render_scan_result(result: ScanResult) -> None:
    output = error_console if result.completeness is ScanCompleteness.FAILED else console
    repository = result.repository.root or result.repository.requested_path
    output.print(f"Repository: {repository}", soft_wrap=True, markup=False)
    output.print(f"Status: {result.completeness.value}", markup=False)

    if result.completeness is not ScanCompleteness.FAILED:
        counts = {artifact_type: 0 for artifact_type in ArtifactType}
        for artifact in result.artifacts:
            counts[artifact.artifact_type] += 1

        table = Table(title="Discovered artifacts")
        table.add_column("Type")
        table.add_column("Count", justify="right")
        for artifact_type in ArtifactType:
            table.add_row(artifact_type.value, str(counts[artifact_type]))
        table.add_section()
        table.add_row("total", str(len(result.artifacts)))
        output.print(table)

        if result.skipped:
            output.print(f"Skipped paths: {len(result.skipped)}", markup=False)
            for skipped_path in result.skipped:
                output.print(f"  {skipped_path.path} ({skipped_path.reason.value})", markup=False)

    if result.warnings:
        output.print("Warnings:")
        for warning in result.warnings:
            location = f" [{warning.path}]" if warning.path else ""
            output.print(f"  {warning.message}{location}", markup=False)

    if result.errors:
        output.print("Errors:")
        for error in result.errors:
            output.print(f"  {error.message}", markup=False)


@app.callback(invoke_without_command=True)
def main(
    context: typer.Context,
    version_requested: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed AgentGuard version and exit.",
        ),
    ] = False,
) -> None:
    """Run AgentGuard."""
    del version_requested
    if context.invoked_subcommand is None:
        typer.echo(context.get_help())


@app.command()
def scan(
    repository_path: Annotated[Path, typer.Argument(help="Repository directory to scan.")],
) -> None:
    """Discover supported artifacts in a repository."""
    result = scan_repository(repository_path)
    _render_scan_result(result)
    if result.completeness is ScanCompleteness.FAILED:
        raise typer.Exit(code=1)
