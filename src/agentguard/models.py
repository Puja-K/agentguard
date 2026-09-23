"""Typed domain models shared across AgentGuard."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


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
