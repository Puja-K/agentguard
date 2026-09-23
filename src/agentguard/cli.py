"""Command-line interface for AgentGuard."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from agentguard.extractors import parse_eval_artifacts
from agentguard.models import (
    ArtifactType,
    EvalParseResult,
    EvalSourceType,
    ScanCompleteness,
    ScanResult,
)
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


def _render_scan_result(result: ScanResult, eval_result: EvalParseResult | None = None) -> None:
    completeness = eval_result.completeness if eval_result is not None else result.completeness
    output = error_console if completeness is ScanCompleteness.FAILED else console
    repository = result.repository.root or result.repository.requested_path
    output.print(f"Repository: {repository}", soft_wrap=True, markup=False)
    output.print(f"Status: {completeness.value}", markup=False)

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

        if eval_result is not None:
            eval_counts = {source_type: 0 for source_type in EvalSourceType}
            for scenario in eval_result.scenarios:
                eval_counts[scenario.source_type] += 1

            eval_table = Table(title="Discovered evals")
            eval_table.add_column("Source")
            eval_table.add_column("Count", justify="right")
            for source_type in EvalSourceType:
                eval_table.add_row(source_type.value, str(eval_counts[source_type]))
            eval_table.add_section()
            eval_table.add_row("total", str(len(eval_result.scenarios)))
            output.print(eval_table)
            output.print(f"Eval parse warnings: {len(eval_result.warnings)}", markup=False)

        if result.skipped:
            output.print(f"Skipped paths: {len(result.skipped)}", markup=False)
            for skipped_path in result.skipped:
                output.print(f"  {skipped_path.path} ({skipped_path.reason.value})", markup=False)

    if result.warnings:
        output.print("Warnings:")
        for scan_warning in result.warnings:
            location = f" [{scan_warning.path}]" if scan_warning.path else ""
            output.print(f"  {scan_warning.message}{location}", markup=False)

    if result.errors:
        output.print("Errors:")
        for scan_error in result.errors:
            output.print(f"  {scan_error.message}", markup=False)

    if eval_result is not None and eval_result.warnings:
        output.print("Eval parse warnings:")
        for eval_warning in eval_result.warnings:
            location = (
                f"{eval_warning.source_file}:{eval_warning.line}"
                if eval_warning.line
                else eval_warning.source_file
            )
            output.print(f"  {eval_warning.message} [{location}]", markup=False)

    if eval_result is not None and eval_result.errors:
        output.print("Eval parse errors:")
        for eval_error in eval_result.errors:
            output.print(f"  {eval_error.message} [{eval_error.source_file}]", markup=False)


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
    eval_result = (
        parse_eval_artifacts(result) if result.completeness is not ScanCompleteness.FAILED else None
    )
    _render_scan_result(result, eval_result)
    if result.completeness is ScanCompleteness.FAILED:
        raise typer.Exit(code=1)
