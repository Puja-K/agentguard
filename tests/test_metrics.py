"""Tests for repository-local V0 validation metrics and exports."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentguard.feedback import FindingStore, InvalidFeedbackReasonError
from agentguard.findings import update_findings
from agentguard.metrics import calculate_validation_summary, export_validation_data
from agentguard.models import (
    AssessmentAvailability,
    Behavior,
    BehaviorAction,
    BehaviorCoverageAssessment,
    BehaviorExtractionResult,
    BehaviorSourceType,
    BehaviorType,
    ConfidenceLevel,
    CoverageStatus,
    FeedbackReason,
    FindingDisposition,
    MatchingResult,
    MetricName,
    ScanCompleteness,
    SourceEvidence,
    ValidationCriterionStatus,
)

FIRST_SCAN = datetime(2026, 1, 1, tzinfo=UTC)


def _behavior(number: int) -> Behavior:
    subject = f"tool_{number}"
    return Behavior(
        behavior_id=f"behavior_{number}",
        description=f"{subject} can be invoked",
        behavior_type=BehaviorType.TOOL_INVOCATION,
        source_type=BehaviorSourceType.PYTHON_TOOL,
        source_file=f"tools/{subject}.py",
        source_symbol=subject,
        subject=subject,
        action=BehaviorAction(kind="call", target=subject),
        evidence=(
            SourceEvidence(
                kind="function",
                source_file=f"tools/{subject}.py",
                source_symbol=subject,
                start_line=2,
                end_line=3,
                excerpt=f"SECRET SOURCE CONTENT {subject}",
            ),
        ),
        confidence=ConfidenceLevel.HIGH,
        extractor="test",
        content_fingerprint=f"fingerprint-{number}",
    )


def _assessment(
    behavior: Behavior,
    *,
    status: CoverageStatus = CoverageStatus.POTENTIALLY_UNCOVERED,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> BehaviorCoverageAssessment:
    return BehaviorCoverageAssessment(
        behavior_id=behavior.behavior_id,
        availability=AssessmentAvailability.AVAILABLE,
        coverage_status=status,
        confidence=confidence,
        matched_eval_ids=("eval_covered",) if status is CoverageStatus.COVERED else (),
        explanation="Deterministic test assessment.",
        candidate_count=1 if status is CoverageStatus.COVERED else 0,
        matcher="test-matcher",
    )


def _scan(
    root: Path,
    behaviors: tuple[Behavior, ...],
    assessments: tuple[BehaviorCoverageAssessment, ...],
    when: datetime,
    completeness: ScanCompleteness = ScanCompleteness.COMPLETE,
) -> None:
    update_findings(
        root,
        BehaviorExtractionResult(behaviors=behaviors, completeness=completeness),
        MatchingResult(
            assessments=assessments,
            completeness=completeness,
            behavior_count=len(behaviors),
            matcher="test-matcher",
        ),
        observed_at=when,
    )


def _create_findings(root: Path, count: int = 1) -> FindingStore:
    behaviors = tuple(_behavior(index) for index in range(count))
    _scan(root, behaviors, tuple(_assessment(item) for item in behaviors), FIRST_SCAN)
    return FindingStore(root)


def _metric(store: FindingStore, name: MetricName):
    summary = calculate_validation_summary(store)
    return next(metric for metric in summary.metrics if metric.name is name)


def test_zero_denominators_report_not_enough_data(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)

    summary = calculate_validation_summary(store)

    assert all(metric.rate is None for metric in summary.metrics)
    assert all(metric.denominator == 0 for metric in summary.metrics)


def test_review_metrics_use_current_dispositions_and_unique_findings(tmp_path: Path) -> None:
    store = _create_findings(tmp_path, 4)
    findings = store.list_findings()
    store.record_feedback(findings[0].finding_id, FindingDisposition.ADD_EVAL)
    store.record_feedback(findings[1].finding_id, FindingDisposition.VALID_LATER)
    store.record_feedback(findings[2].finding_id, FindingDisposition.ALREADY_COVERED)
    store.record_feedback(findings[3].finding_id, FindingDisposition.NOT_RELEVANT)
    store.record_feedback(findings[3].finding_id, FindingDisposition.VALID_LATER)

    assert _metric(store, MetricName.VALID_GAP_RATE).rate == pytest.approx(0.75)
    assert _metric(store, MetricName.INTENT_TO_ACT_RATE).rate == pytest.approx(0.25)
    assert _metric(store, MetricName.FALSE_POSITIVE_RATE).rate == pytest.approx(0.25)
    assert _metric(store, MetricName.VALID_GAP_RATE).denominator == 4


def test_add_eval_is_intent_and_not_confirmed_impact(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    store.record_feedback(finding.finding_id, FindingDisposition.ADD_EVAL)

    assert _metric(store, MetricName.INTENT_TO_ACT_RATE).rate == 1.0
    assert _metric(store, MetricName.CONFIRMED_IMPACT_RATE).rate == 0.0


def test_explicit_confirmation_is_required_for_confirmed_impact(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    store.record_feedback(finding.finding_id, FindingDisposition.ADD_EVAL)
    store.confirm_impact(finding.finding_id)

    metric = _metric(store, MetricName.CONFIRMED_IMPACT_RATE)

    assert metric.numerator == 1
    assert metric.rate == 1.0


def test_not_relevant_is_not_a_false_positive(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    store.record_feedback(finding.finding_id, FindingDisposition.NOT_RELEVANT)

    metric = _metric(store, MetricName.FALSE_POSITIVE_RATE)

    assert metric.denominator == 1
    assert metric.numerator == 0


def test_suppression_requires_reason_for_review_eligibility(tmp_path: Path) -> None:
    store = _create_findings(tmp_path, 2)
    first, second = store.list_findings()
    store.record_feedback(first.finding_id, FindingDisposition.SUPPRESSED)
    store.record_feedback(second.finding_id, FindingDisposition.SUPPRESSED, reason="duplicate")

    metric = _metric(store, MetricName.VALID_GAP_RATE)

    assert metric.denominator == 1
    assert metric.cohort.eligible_finding_ids == (second.finding_id,)


def test_first_review_confidence_is_frozen(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    store.record_feedback(finding.finding_id, FindingDisposition.ADD_EVAL)
    behavior = _behavior(0)
    _scan(
        tmp_path,
        (behavior,),
        (_assessment(behavior, status=CoverageStatus.COVERED, confidence=ConfidenceLevel.MEDIUM),),
        FIRST_SCAN + timedelta(days=1),
    )

    metric = _metric(store, MetricName.CONFIRMED_IMPACT_RATE)

    assert store.get_finding(finding.finding_id).current_confidence is ConfidenceLevel.MEDIUM
    assert metric.denominator == 1


def test_observed_resolution_is_distinct_from_confirmed_impact(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    behavior = _behavior(0)
    _scan(
        tmp_path,
        (behavior,),
        (_assessment(behavior, status=CoverageStatus.COVERED),),
        FIRST_SCAN + timedelta(days=1),
    )

    observed = _metric(store, MetricName.OBSERVED_RESOLUTION_RATE)
    resolved = _metric(store, MetricName.RESOLVED_BY_TEST_RATE)
    confirmed = _metric(store, MetricName.CONFIRMED_IMPACT_RATE)

    assert observed.rate == 1.0
    assert resolved.rate == 1.0
    assert confirmed.rate is None
    assert not store.get_finding(finding.finding_id).confirmed_impact


def test_reopened_finding_is_counted_once(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    behavior = _behavior(0)
    _scan(
        tmp_path,
        (behavior,),
        (_assessment(behavior, status=CoverageStatus.COVERED),),
        FIRST_SCAN + timedelta(days=1),
    )
    _scan(
        tmp_path,
        (behavior,),
        (_assessment(behavior),),
        FIRST_SCAN + timedelta(days=2),
    )

    metric = _metric(store, MetricName.OBSERVED_RESOLUTION_RATE)

    assert metric.numerator == 1
    assert metric.denominator == 1


def test_incomplete_scan_excludes_unavailable_finding_until_complete_scan(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    store.record_feedback(finding.finding_id, FindingDisposition.ADD_EVAL)
    _scan(
        tmp_path,
        (),
        (),
        FIRST_SCAN + timedelta(days=1),
        ScanCompleteness.INCOMPLETE,
    )

    assert _metric(store, MetricName.VALID_GAP_RATE).denominator == 0

    behavior = _behavior(0)
    _scan(
        tmp_path,
        (behavior,),
        (_assessment(behavior),),
        FIRST_SCAN + timedelta(days=2),
    )
    assert _metric(store, MetricName.VALID_GAP_RATE).denominator == 1


def test_breakdowns_cover_required_dimensions_and_rejection_reason(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]
    store.record_feedback(
        finding.finding_id,
        FindingDisposition.ALREADY_COVERED,
        feedback_reason=FeedbackReason.FIXTURE_INDIRECTION,
    )

    summary = calculate_validation_summary(store)
    dimensions = {item.dimension for item in summary.breakdowns}

    assert dimensions == {
        "behavior_type",
        "confidence",
        "coverage_status",
        "rejection_reason",
        "source_file",
    }
    rejection = next(
        item
        for item in summary.breakdowns
        if item.dimension == "rejection_reason" and item.value == "fixture_indirection"
    )
    assert rejection.already_covered == 1


def test_rejection_reason_taxonomy_is_validated_and_persisted(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    finding = store.list_findings()[0]

    with pytest.raises(InvalidFeedbackReasonError):
        store.record_feedback(
            finding.finding_id,
            FindingDisposition.ADD_EVAL,
            feedback_reason=FeedbackReason.ALIAS_OR_WRAPPER,
        )

    updated = store.record_feedback(
        finding.finding_id,
        FindingDisposition.NOT_RELEVANT,
        feedback_reason=FeedbackReason.IMPLEMENTATION_DETAIL,
    )
    assert updated.current_feedback_reason is FeedbackReason.IMPLEMENTATION_DETAIL
    assert (
        store.feedback_events(finding.finding_id)[0].feedback_reason
        is FeedbackReason.IMPLEMENTATION_DETAIL
    )


def test_json_export_contains_no_source_contents(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)

    export = export_validation_data(store)
    serialized = str(export)

    assert "SECRET SOURCE CONTENT" not in serialized
    assert export["summary"]["repository"] == str(tmp_path)
    assert export["findings"][0]["finding_id"]


def test_progress_criteria_are_reported_without_overall_verdict(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)

    summary = calculate_validation_summary(store)
    criteria = {criterion.name: criterion for criterion in summary.criteria}

    assert criteria["repositories_evaluated"].current == "1"
    assert criteria["valid_high_confidence_findings"].status is (
        ValidationCriterionStatus.NOT_ENOUGH_DATA
    )
    assert criteria["repeat_scan_evidence"].status is ValidationCriterionStatus.NOT_YET


def test_repeat_scan_counting_uses_persisted_scan_history(tmp_path: Path) -> None:
    store = _create_findings(tmp_path)
    behavior = _behavior(0)
    _scan(
        tmp_path,
        (behavior,),
        (_assessment(behavior),),
        FIRST_SCAN + timedelta(days=1),
    )

    summary = calculate_validation_summary(store)
    repeat_scan = next(
        criterion for criterion in summary.criteria if criterion.name == "repeat_scan_evidence"
    )

    assert summary.scan_count == 2
    assert repeat_scan.status is ValidationCriterionStatus.PASS
