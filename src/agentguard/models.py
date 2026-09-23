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
    """Inspectible source evidence for an extracted eval fact."""

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
