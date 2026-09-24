"""SQLite persistence for local findings, feedback, and lifecycle history."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import JsonValue

from agentguard.models import (
    FeedbackEvent,
    Finding,
    FindingDisposition,
    FindingHistoryEvent,
    FindingHistoryEventType,
    FindingScanRecord,
    ImpactConfirmationEvent,
)

STATE_DIRECTORY = ".agentguard"
DATABASE_FILENAME = "agentguard.db"


class FindingNotFoundError(LookupError):
    """Raised when a requested finding does not exist in local state."""


class FindingStore:
    """Repository-scoped SQLite storage with append-only event tables."""

    def __init__(self, repository_root: str | Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.state_directory = self.repository_root / STATE_DIRECTORY
        self.database_path = self.state_directory / DATABASE_FILENAME

    @property
    def exists(self) -> bool:
        """Return whether this repository already has AgentGuard state."""
        return self.database_path.is_file()

    def initialize(self) -> None:
        """Create repository-local state and schema when needed."""
        self.state_directory.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    behavior_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    disposition TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS finding_history (
                    event_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS finding_history_finding_id
                    ON finding_history(finding_id, occurred_at);
                CREATE TABLE IF NOT EXISTS feedback_events (
                    event_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS feedback_events_finding_id
                    ON feedback_events(finding_id, occurred_at);
                CREATE TABLE IF NOT EXISTS impact_events (
                    event_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS impact_events_finding_id
                    ON impact_events(finding_id, occurred_at);
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    completeness TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _upsert_finding(connection: sqlite3.Connection, finding: Finding) -> None:
        connection.execute(
            """
            INSERT INTO findings(finding_id, behavior_id, status, disposition, payload)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(finding_id) DO UPDATE SET
                behavior_id = excluded.behavior_id,
                status = excluded.status,
                disposition = excluded.disposition,
                payload = excluded.payload
            """,
            (
                finding.finding_id,
                finding.behavior_id,
                finding.status.value,
                finding.current_disposition.value if finding.current_disposition else None,
                finding.model_dump_json(),
            ),
        )

    def persist_scan(
        self,
        findings: tuple[Finding, ...],
        history: tuple[FindingHistoryEvent, ...],
        scan_record: FindingScanRecord,
    ) -> None:
        """Atomically persist current findings and events for one scan."""
        self.initialize()
        with self._connect() as connection:
            for finding in findings:
                self._upsert_finding(connection, finding)
            for event in history:
                connection.execute(
                    """
                    INSERT INTO finding_history(
                        event_id, finding_id, event_type, occurred_at, payload
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.finding_id,
                        event.event_type.value,
                        event.occurred_at.isoformat(),
                        event.model_dump_json(),
                    ),
                )
            connection.execute(
                """
                INSERT INTO scans(scan_id, occurred_at, completeness, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    scan_record.scan_id,
                    scan_record.occurred_at.isoformat(),
                    scan_record.completeness.value,
                    scan_record.model_dump_json(),
                ),
            )

    def list_findings(self) -> tuple[Finding, ...]:
        """Load all current findings without creating state for an unscanned repository."""
        if not self.exists:
            return ()
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM findings ORDER BY finding_id").fetchall()
        return tuple(Finding.model_validate_json(row["payload"]) for row in rows)

    def get_finding(self, finding_id: str) -> Finding:
        """Load one current finding or raise a user-facing lookup error."""
        if not self.exists:
            raise FindingNotFoundError(f"Finding does not exist: {finding_id}")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM findings WHERE finding_id = ?", (finding_id,)
            ).fetchone()
        if row is None:
            raise FindingNotFoundError(f"Finding does not exist: {finding_id}")
        return Finding.model_validate_json(row["payload"])

    def record_feedback(
        self,
        finding_id: str,
        disposition: FindingDisposition,
        *,
        reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Finding:
        """Append feedback and update the finding's current disposition."""
        timestamp = occurred_at or datetime.now(UTC)
        finding = self.get_finding(finding_id)
        event = FeedbackEvent(
            event_id=f"feedback_{uuid4().hex}",
            finding_id=finding_id,
            disposition=disposition,
            occurred_at=timestamp,
            reason=reason,
            confidence_at_feedback=finding.current_confidence,
        )
        details: dict[str, JsonValue] = {"disposition": disposition.value}
        if reason is not None:
            details["reason"] = reason
        history = FindingHistoryEvent(
            event_id=f"history_{uuid4().hex}",
            finding_id=finding_id,
            event_type=FindingHistoryEventType.FEEDBACK,
            occurred_at=timestamp,
            details=details,
        )
        updated = finding.model_copy(update={"current_disposition": disposition})
        with self._connect() as connection:
            self._upsert_finding(connection, updated)
            connection.execute(
                """
                INSERT INTO feedback_events(
                    event_id, finding_id, disposition, occurred_at, payload
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.finding_id,
                    event.disposition.value,
                    event.occurred_at.isoformat(),
                    event.model_dump_json(),
                ),
            )
            self._insert_history(connection, history)
        return updated

    def confirm_impact(
        self,
        finding_id: str,
        *,
        note: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Finding:
        """Record explicit user-confirmed product impact."""
        timestamp = occurred_at or datetime.now(UTC)
        finding = self.get_finding(finding_id)
        event = ImpactConfirmationEvent(
            event_id=f"impact_{uuid4().hex}",
            finding_id=finding_id,
            occurred_at=timestamp,
            note=note,
        )
        details: dict[str, JsonValue] = {"confirmed_impact": True}
        if note is not None:
            details["note"] = note
        history = FindingHistoryEvent(
            event_id=f"history_{uuid4().hex}",
            finding_id=finding_id,
            event_type=FindingHistoryEventType.IMPACT_CONFIRMED,
            occurred_at=timestamp,
            details=details,
        )
        updated = finding.model_copy(update={"confirmed_impact": True})
        with self._connect() as connection:
            self._upsert_finding(connection, updated)
            connection.execute(
                """
                INSERT INTO impact_events(event_id, finding_id, occurred_at, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.finding_id,
                    event.occurred_at.isoformat(),
                    event.model_dump_json(),
                ),
            )
            self._insert_history(connection, history)
        return updated

    @staticmethod
    def _insert_history(connection: sqlite3.Connection, event: FindingHistoryEvent) -> None:
        connection.execute(
            """
            INSERT INTO finding_history(event_id, finding_id, event_type, occurred_at, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.finding_id,
                event.event_type.value,
                event.occurred_at.isoformat(),
                event.model_dump_json(),
            ),
        )

    def history(self, finding_id: str) -> tuple[FindingHistoryEvent, ...]:
        """Load append-only lifecycle history for one finding."""
        if not self.exists:
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM finding_history
                WHERE finding_id = ? ORDER BY occurred_at, event_id
                """,
                (finding_id,),
            ).fetchall()
        return tuple(FindingHistoryEvent.model_validate_json(row["payload"]) for row in rows)

    def feedback_events(self, finding_id: str) -> tuple[FeedbackEvent, ...]:
        """Load all feedback revisions for one finding."""
        if not self.exists:
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM feedback_events
                WHERE finding_id = ? ORDER BY occurred_at, event_id
                """,
                (finding_id,),
            ).fetchall()
        return tuple(FeedbackEvent.model_validate_json(row["payload"]) for row in rows)

    def impact_events(self, finding_id: str) -> tuple[ImpactConfirmationEvent, ...]:
        """Load explicit impact confirmations for one finding."""
        if not self.exists:
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM impact_events
                WHERE finding_id = ? ORDER BY occurred_at, event_id
                """,
                (finding_id,),
            ).fetchall()
        return tuple(ImpactConfirmationEvent.model_validate_json(row["payload"]) for row in rows)

    def scan_records(self) -> tuple[FindingScanRecord, ...]:
        """Load persisted scan records for later lifecycle metrics."""
        if not self.exists:
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM scans ORDER BY occurred_at, scan_id"
            ).fetchall()
        return tuple(FindingScanRecord.model_validate_json(row["payload"]) for row in rows)
