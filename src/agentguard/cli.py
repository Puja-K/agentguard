"""Command-line interface for AgentGuard."""

from importlib.metadata import version
from typing import Annotated

import typer

PACKAGE_NAME = "agentguard"

app = typer.Typer(
    help="Find potentially important AI-agent behaviors that lack adequate eval coverage.",
    invoke_without_command=True,
    no_args_is_help=False,
)


def get_version() -> str:
    """Return the version from the installed package metadata."""
    return version(PACKAGE_NAME)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(get_version())
        raise typer.Exit()


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
