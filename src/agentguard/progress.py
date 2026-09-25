"""Terminal progress reporting for CLI orchestration."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console

from agentguard.models import ScanCompleteness


class ScanProgressReporter:
    """Render concise phase progress without coupling UI to scan logic."""

    def __init__(self, console: Console, *, enabled: bool = True) -> None:
        self.console = console
        self.enabled = enabled

    def start(self, repository: Path) -> None:
        """Announce a scan before its first potentially slow phase."""
        if self.enabled:
            self.console.print(f"Scanning {repository}", markup=False, soft_wrap=True)

    @contextmanager
    def phase(self, active_label: str, result_label: str) -> Iterator[None]:
        """Show one active phase and clean it up even when work raises."""
        if not self.enabled:
            yield
            return

        try:
            if self.console.is_terminal:
                with self.console.status(f"{active_label}...", spinner="dots"):
                    yield
            else:
                self.console.print(f"{active_label}...", markup=False)
                yield
        except Exception:
            self.console.print(f"✗ {result_label} failed", style="red", markup=False)
            raise

    def complete(
        self,
        label: str,
        completeness: ScanCompleteness,
        *,
        detail: str | None = None,
    ) -> None:
        """Render the truthful terminal state of a completed phase."""
        if not self.enabled:
            return

        if completeness is ScanCompleteness.COMPLETE:
            marker, state, style = "✓", "complete", "green"
        elif completeness is ScanCompleteness.INCOMPLETE:
            marker, state, style = "!", "incomplete", "yellow"
        else:
            marker, state, style = "✗", "failed", "red"
        suffix = f" — {detail}" if detail else ""
        self.console.print(
            f"{marker} {label} {state}{suffix}",
            style=style,
            markup=False,
        )
