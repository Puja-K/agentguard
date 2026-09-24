"""Command-line interface for AgentGuard."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from agentguard.extractors import extract_behaviors, parse_eval_artifacts
from agentguard.matchers import match_behaviors_to_evals
from agentguard.models import (
    ArtifactType,
    AssessmentAvailability,
    BehaviorExtractionResult,
    BehaviorType,
    CoverageStatus,
    EvalParseResult,
    EvalSourceType,
    MatchingResult,
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


def _combined_completeness(
    result: ScanResult,
    eval_result: EvalParseResult | None,
    behavior_result: BehaviorExtractionResult | None,
    matching_result: MatchingResult | None,
) -> ScanCompleteness:
    statuses = [result.completeness]
    statuses.extend(
        extraction.completeness
        for extraction in (eval_result, behavior_result, matching_result)
        if extraction is not None
    )
    if ScanCompleteness.FAILED in statuses:
        return ScanCompleteness.FAILED
    if ScanCompleteness.INCOMPLETE in statuses:
        return ScanCompleteness.INCOMPLETE
    return ScanCompleteness.COMPLETE


def _render_scan_result(
    result: ScanResult,
    eval_result: EvalParseResult | None = None,
    behavior_result: BehaviorExtractionResult | None = None,
    matching_result: MatchingResult | None = None,
) -> None:
    completeness = _combined_completeness(result, eval_result, behavior_result, matching_result)
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

        if behavior_result is not None:
            behavior_counts = {behavior_type: 0 for behavior_type in BehaviorType}
            for behavior in behavior_result.behaviors:
                behavior_counts[behavior.behavior_type] += 1

            behavior_table = Table(title="Detected behaviors")
            behavior_table.add_column("Type")
            behavior_table.add_column("Count", justify="right")
            for behavior_type in BehaviorType:
                behavior_table.add_row(behavior_type.value, str(behavior_counts[behavior_type]))
            behavior_table.add_section()
            behavior_table.add_row("total", str(len(behavior_result.behaviors)))
            output.print(behavior_table)
            output.print(
                f"Behavior extraction warnings: {len(behavior_result.warnings)}",
                markup=False,
            )

        if matching_result is not None:
            coverage_counts = {status: 0 for status in CoverageStatus}
            unavailable = 0
            for assessment in matching_result.assessments:
                if assessment.availability is AssessmentAvailability.UNAVAILABLE:
                    unavailable += 1
                elif assessment.coverage_status is not None:
                    coverage_counts[assessment.coverage_status] += 1

            matching_table = Table(title="Coverage assessments")
            matching_table.add_column("Status")
            matching_table.add_column("Count", justify="right")
            for status in CoverageStatus:
                matching_table.add_row(status.value, str(coverage_counts[status]))
            matching_table.add_row("unavailable", str(unavailable))
            output.print(matching_table)
            output.print(
                f"Candidate pairs considered: {matching_result.candidate_pair_count}",
                markup=False,
            )

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

    if behavior_result is not None and behavior_result.warnings:
        output.print("Behavior extraction warnings:")
        for behavior_warning in behavior_result.warnings:
            location = (
                f"{behavior_warning.source_file}:{behavior_warning.line}"
                if behavior_warning.line
                else behavior_warning.source_file
            )
            output.print(f"  {behavior_warning.message} [{location}]", markup=False)

    if behavior_result is not None and behavior_result.errors:
        output.print("Behavior extraction errors:")
        for behavior_error in behavior_result.errors:
            output.print(f"  {behavior_error.message} [{behavior_error.source_file}]", markup=False)

    if matching_result is not None and matching_result.warnings:
        output.print("Matching warnings:")
        for matching_warning in matching_result.warnings:
            output.print(f"  {matching_warning.message}", markup=False)

    if matching_result is not None and matching_result.errors:
        output.print("Matching errors:")
        for matching_error in matching_result.errors:
            output.print(f"  {matching_error.message}", markup=False)


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
    """Discover artifacts and assess deterministic behavior coverage."""
    result = scan_repository(repository_path)
    eval_result = (
        parse_eval_artifacts(result) if result.completeness is not ScanCompleteness.FAILED else None
    )
    behavior_result = (
        extract_behaviors(result) if result.completeness is not ScanCompleteness.FAILED else None
    )
    matching_result = (
        match_behaviors_to_evals(behavior_result, eval_result)
        if behavior_result is not None and eval_result is not None
        else None
    )
    _render_scan_result(result, eval_result, behavior_result, matching_result)
    if result.completeness is ScanCompleteness.FAILED:
        raise typer.Exit(code=1)
