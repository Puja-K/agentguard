"""Selection helpers for the interactive local review workflow."""

from agentguard.models import Finding, FindingStatus


def review_queue(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Return open, assessable findings without an explicit disposition."""
    return tuple(
        finding
        for finding in sorted(findings, key=lambda item: item.finding_id)
        if finding.status is FindingStatus.OPEN
        and finding.assessment_available
        and finding.current_disposition is None
    )
