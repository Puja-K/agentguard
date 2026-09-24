"""Typed domain models shared across AgentGuard."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ArtifactType(StrEnum):
    """Artifact categories supported by V0 discovery."""

    PYTHON = "python"
    PROMPT_TEXT = "prompt_text"
    PROMPT_MARKDOWN = "prompt_markdown"
    EVAL_JSONL = "eval_jsonl"


class ScanCompleteness(StrEnum):
    """Whether repository discovery examined everything required."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class ConfidenceLevel(StrEnum):
    """Qualitative confidence in a deterministic or inferred result."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvalSourceType(StrEnum):
    """Supported sources of eval scenarios."""

    PYTEST = "pytest"
    JSONL = "jsonl"


class EvalAssertionKind(StrEnum):
    """Static assertion patterns recognized in an eval."""

    ASSERT = "assert"
    EXPECTED_EXCEPTION = "expected_exception"


class BehaviorType(StrEnum):
    """Deterministic behavior categories supported by V0 extraction."""

    TOOL_INVOCATION = "tool_invocation"
    TOOL_FAILURE = "tool_failure"
    CONDITIONAL_BRANCH = "conditional_branch"
    WORKFLOW_TRANSITION = "workflow_transition"
    FALLBACK = "fallback"
    ESCALATION = "escalation"


class BehaviorSourceType(StrEnum):
    """Static source constructs that produce behaviors."""

    PYTHON_TOOL = "python_tool"
    LANGGRAPH_WORKFLOW = "langgraph_workflow"


class CoverageStatus(StrEnum):
    """Supported V0 behavior coverage classifications."""

    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    POTENTIALLY_UNCOVERED = "potentially_uncovered"


class AssessmentAvailability(StrEnum):
    """Whether available evidence supports a coverage classification."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class SkipReason(StrEnum):
    """Why a path was not included as a discovered artifact."""

    EXCLUDED = "excluded"
    UNREADABLE = "unreadable"
    UNSUPPORTED = "unsupported"


class DomainModel(BaseModel):
    """Immutable base for machine-readable AgentGuard domain models."""

    model_config = ConfigDict(frozen=True)


class RepositoryMetadata(DomainModel):
    """Repository and effective configuration used for discovery."""

    requested_path: str
    root: str | None = None
    config_path: str | None = None
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


class DiscoveredArtifact(DomainModel):
    """A readable, supported artifact found in the repository."""

    path: str
    artifact_type: ArtifactType
    size_bytes: int


class SkippedPath(DomainModel):
    """A relevant path intentionally or necessarily skipped."""

    path: str
    reason: SkipReason
    is_directory: bool = False


class ScanWarning(DomainModel):
    """A non-fatal problem that limited repository discovery."""

    code: str
    message: str
    path: str | None = None


class ScanError(DomainModel):
    """A fatal problem that prevented repository discovery."""

    code: str
    message: str
    path: str | None = None


class ScanResult(DomainModel):
    """Deterministic manifest produced by repository discovery."""

    repository: RepositoryMetadata
    artifacts: tuple[DiscoveredArtifact, ...] = ()
    skipped: tuple[SkippedPath, ...] = ()
    warnings: tuple[ScanWarning, ...] = ()
    errors: tuple[ScanError, ...] = ()
    completeness: ScanCompleteness


class SourceEvidence(DomainModel):
    """Inspectible source evidence for an extracted static fact."""

    kind: str
    source_file: str
    source_symbol: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    excerpt: str


class LiteralArgument(DomainModel):
    """A statically recoverable literal call argument."""

    position: int | None = None
    keyword: str | None = None
    value: JsonValue


class ReferencedSymbol(DomainModel):
    """A function, tool, or other callable referenced by an eval."""

    name: str
    qualified_name: str
    literal_arguments: tuple[LiteralArgument, ...] = ()
    evidence: SourceEvidence


class EvalAssertion(DomainModel):
    """An assertion or expected-exception construct found statically."""

    kind: EvalAssertionKind
    expression: str
    expected_exception: str | None = None
    evidence: SourceEvidence


class ExpectedOutcome(DomainModel):
    """An expected result explicitly stated by an eval artifact."""

    description: str
    value: JsonValue | None = None
    is_explicit: bool = True


class EvalScenario(DomainModel):
    """A normalized pytest test or JSONL eval scenario."""

    eval_id: str
    source_type: EvalSourceType
    source_file: str
    source_symbol: str | None = None
    name: str
    description: str | None = None
    inputs: JsonValue | None = None
    expected_outcome: ExpectedOutcome | None = None
    assertions: tuple[EvalAssertion, ...] = ()
    referenced_symbols: tuple[ReferencedSymbol, ...] = ()
    evidence: tuple[SourceEvidence, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    unknown_fields: dict[str, JsonValue] = Field(default_factory=dict)
    content_fingerprint: str
    confidence: ConfidenceLevel


class EvalParseWarning(DomainModel):
    """A non-fatal limitation encountered while parsing eval artifacts."""

    code: str
    message: str
    source_file: str
    line: int | None = None


class EvalParseError(DomainModel):
    """An artifact-level failure encountered while parsing evals."""

    code: str
    message: str
    source_file: str


class EvalParseResult(DomainModel):
    """Typed result of parsing discovered artifacts for eval scenarios."""

    scenarios: tuple[EvalScenario, ...] = ()
    warnings: tuple[EvalParseWarning, ...] = ()
    errors: tuple[EvalParseError, ...] = ()
    completeness: ScanCompleteness


class BehaviorCondition(DomainModel):
    """A statically recoverable condition governing a behavior."""

    expression: str
    normalized_expression: str


class BehaviorAction(DomainModel):
    """The explicit action or outcome associated with a behavior."""

    kind: str
    target: str | None = None
    outcome: str | None = None


class ToolArgument(DomainModel):
    """A statically declared tool argument."""

    name: str
    required: bool
    annotation: str | None = None
    default: str | None = None


class Behavior(DomainModel):
    """A normalized deterministic behavior extracted from repository source."""

    behavior_id: str
    description: str
    behavior_type: BehaviorType
    source_type: BehaviorSourceType
    source_file: str
    source_symbol: str | None = None
    subject: str
    condition: BehaviorCondition | None = None
    action: BehaviorAction | None = None
    arguments: tuple[ToolArgument, ...] = ()
    evidence: tuple[SourceEvidence, ...] = ()
    confidence: ConfidenceLevel
    extractor: str
    content_fingerprint: str


class BehaviorExtractionWarning(DomainModel):
    """A non-fatal limitation encountered while extracting behaviors."""

    code: str
    message: str
    source_file: str
    line: int | None = None


class BehaviorExtractionError(DomainModel):
    """An artifact-level behavior extraction failure."""

    code: str
    message: str
    source_file: str


class BehaviorExtractionResult(DomainModel):
    """Typed result of deterministic behavior extraction."""

    behaviors: tuple[Behavior, ...] = ()
    warnings: tuple[BehaviorExtractionWarning, ...] = ()
    errors: tuple[BehaviorExtractionError, ...] = ()
    completeness: ScanCompleteness


class MatchEvidence(DomainModel):
    """Decomposed deterministic evidence for one behavior/eval candidate pair."""

    candidate_reasons: tuple[str, ...] = ()
    same_subject: bool = False
    condition_matches: bool = False
    branch_matches: bool = False
    failure_matches: bool = False
    action_matches: bool = False
    explicit_assertion: bool = False
    expected_outcome_present: bool = False
    details: tuple[str, ...] = ()


class BehaviorEvalMatch(DomainModel):
    """The deterministic relationship between a behavior and candidate eval."""

    eval_id: str
    coverage_status: CoverageStatus | None = None
    confidence: ConfidenceLevel
    evidence: MatchEvidence


class BehaviorCoverageAssessment(DomainModel):
    """Coverage assessment for one extracted behavior."""

    behavior_id: str
    availability: AssessmentAvailability
    coverage_status: CoverageStatus | None = None
    confidence: ConfidenceLevel
    matched_eval_ids: tuple[str, ...] = ()
    matches: tuple[BehaviorEvalMatch, ...] = ()
    explanation: str
    candidate_count: int
    matcher: str


class MatchingWarning(DomainModel):
    """A non-fatal limitation encountered during matching."""

    code: str
    message: str
    behavior_id: str | None = None


class MatchingError(DomainModel):
    """A fatal or behavior-level matching failure."""

    code: str
    message: str
    behavior_id: str | None = None


class MatchingResult(DomainModel):
    """Deterministic behavior-to-eval matching output."""

    assessments: tuple[BehaviorCoverageAssessment, ...] = ()
    warnings: tuple[MatchingWarning, ...] = ()
    errors: tuple[MatchingError, ...] = ()
    completeness: ScanCompleteness
    behavior_count: int = 0
    eval_count: int = 0
    candidate_pair_count: int = 0
    matcher: str
