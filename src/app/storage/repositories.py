"""Repositories for Phase 1 canonical records and durable state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.contracts.models import (
    CommentRecord,
    CounterObservation,
    GroupRecord,
    JobState,
    PostRecord,
)


class RepositoryError(RuntimeError):
    """Base repository failure."""


class RecordNotFound(RepositoryError):
    """Raised when a required durable record is absent."""


class CaptureMetadataConflict(RepositoryError):
    """Raised when immutable capture metadata conflicts."""


class InvalidStateTransition(RepositoryError):
    """Raised when a durable job transition is not allowed."""


ALLOWED_JOB_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PLANNED: frozenset({JobState.RUNNING, JobState.CANCELLED}),
    JobState.RUNNING: frozenset(
        {
            JobState.PARTIAL,
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.INTERRUPTED,
            JobState.CANCELLED,
        }
    ),
    JobState.PARTIAL: frozenset(
        {JobState.RUNNING, JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
    ),
    JobState.INTERRUPTED: frozenset({JobState.RUNNING, JobState.CANCELLED}),
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


def _timestamp(value: datetime) -> str:
    return value.isoformat()


class RawCaptureMetadataRepository:
    """Store immutable raw-capture metadata without capture bytes."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(
        self,
        *,
        capture_id: str,
        sha256: str,
        source_url: str,
        collected_at: datetime,
    ) -> None:
        """Insert capture metadata or verify the existing immutable record."""
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO raw_captures(
                    capture_id, sha256, source_url, collected_at
                ) VALUES (?, ?, ?, ?)
                """,
                (capture_id, sha256, source_url, _timestamp(collected_at)),
            )
            row = self._connection.execute(
                """
                SELECT sha256, source_url, collected_at
                FROM raw_captures
                WHERE capture_id = ?
                """,
                (capture_id,),
            ).fetchone()

        expected = (sha256, source_url, _timestamp(collected_at))
        actual = (row["sha256"], row["source_url"], row["collected_at"])
        if actual != expected:
            message = f"capture metadata conflict: {capture_id}"
            raise CaptureMetadataConflict(message)


class CanonicalRepository:
    """Persist versioned canonical records and immutable counter observations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save_group(self, record: GroupRecord) -> None:
        """Upsert the current Group record and append its counter observation."""
        payload = record.model_dump_json()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO groups(
                    group_id, canonical_url, observed_at, raw_capture_id,
                    schema_version, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    canonical_url = excluded.canonical_url,
                    observed_at = excluded.observed_at,
                    raw_capture_id = excluded.raw_capture_id,
                    schema_version = excluded.schema_version,
                    payload_json = excluded.payload_json
                """,
                (
                    record.group_id,
                    str(record.canonical_url),
                    _timestamp(record.observed_at),
                    record.raw_capture_id,
                    record.schema_version,
                    payload,
                ),
            )
            if record.member_count is not None:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO counter_observations(
                        entity_type, entity_id, metric, observed_at, value,
                        raw_capture_id
                    ) VALUES ('group', ?, 'member_count', ?, ?, ?)
                    """,
                    (
                        record.group_id,
                        _timestamp(record.observed_at),
                        record.member_count,
                        record.raw_capture_id,
                    ),
                )

    def get_group(self, group_id: str) -> GroupRecord | None:
        """Return the current normalized Group record."""
        row = self._connection.execute(
            "SELECT payload_json FROM groups WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        if row is None:
            return None
        return GroupRecord.model_validate_json(row["payload_json"])

    def save_post(self, record: PostRecord) -> None:
        """Upsert one Post and append every changing counter observation."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO posts(
                    post_id, group_id, canonical_url, observed_at, raw_capture_id,
                    schema_version, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    group_id = excluded.group_id,
                    canonical_url = excluded.canonical_url,
                    observed_at = excluded.observed_at,
                    raw_capture_id = excluded.raw_capture_id,
                    schema_version = excluded.schema_version,
                    payload_json = excluded.payload_json
                """,
                (
                    record.post_id,
                    record.group_id,
                    str(record.canonical_url),
                    _timestamp(record.observed_at),
                    record.raw_capture_id,
                    record.schema_version,
                    record.model_dump_json(),
                ),
            )
            self._save_counter(
                "post",
                record.post_id,
                "comments_count",
                record.observed_at,
                record.comments_count,
                record.raw_capture_id,
            )
            self._save_counter(
                "post",
                record.post_id,
                "shares_count",
                record.observed_at,
                record.shares_count,
                record.raw_capture_id,
            )
            for reaction, value in sorted(record.reactions.items()):
                self._save_counter(
                    "post",
                    record.post_id,
                    f"reaction:{reaction}",
                    record.observed_at,
                    value,
                    record.raw_capture_id,
                )

    def get_post(self, post_id: str) -> PostRecord | None:
        """Return the current normalized Post record."""
        row = self._connection.execute(
            "SELECT payload_json FROM posts WHERE post_id = ?",
            (post_id,),
        ).fetchone()
        if row is None:
            return None
        return PostRecord.model_validate_json(row["payload_json"])

    def save_comment(self, record: CommentRecord) -> None:
        """Upsert one top-level Comment and append reaction observations."""
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO comments(
                    comment_id, post_id, group_id, parent_comment_id, observed_at,
                    raw_capture_id, schema_version, payload_json
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
                ON CONFLICT(comment_id) DO UPDATE SET
                    post_id = excluded.post_id,
                    group_id = excluded.group_id,
                    parent_comment_id = NULL,
                    observed_at = excluded.observed_at,
                    raw_capture_id = excluded.raw_capture_id,
                    schema_version = excluded.schema_version,
                    payload_json = excluded.payload_json
                """,
                (
                    record.comment_id,
                    record.post_id,
                    record.group_id,
                    _timestamp(record.observed_at),
                    record.raw_capture_id,
                    record.schema_version,
                    record.model_dump_json(),
                ),
            )
            for reaction, value in sorted(record.reactions.items()):
                self._save_counter(
                    "comment",
                    record.comment_id,
                    f"reaction:{reaction}",
                    record.observed_at,
                    value,
                    record.raw_capture_id,
                )

    def get_comment(self, comment_id: str) -> CommentRecord | None:
        """Return the current normalized Comment record."""
        row = self._connection.execute(
            "SELECT payload_json FROM comments WHERE comment_id = ?",
            (comment_id,),
        ).fetchone()
        if row is None:
            return None
        return CommentRecord.model_validate_json(row["payload_json"])

    def counter_observations(
        self,
        entity_type: str,
        entity_id: str,
        metric: str,
    ) -> list[CounterObservation]:
        """Return immutable counter history in observation order."""
        rows = self._connection.execute(
            """
            SELECT entity_type, entity_id, metric, observed_at, value, raw_capture_id
            FROM counter_observations
            WHERE entity_type = ? AND entity_id = ? AND metric = ?
            ORDER BY observed_at, observation_id
            """,
            (entity_type, entity_id, metric),
        ).fetchall()
        return [CounterObservation.model_validate(dict(row)) for row in rows]

    def _save_counter(
        self,
        entity_type: str,
        entity_id: str,
        metric: str,
        observed_at: datetime,
        value: int,
        raw_capture_id: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO counter_observations(
                entity_type, entity_id, metric, observed_at, value, raw_capture_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                metric,
                _timestamp(observed_at),
                value,
                raw_capture_id,
            ),
        )


class JobRepository:
    """Create jobs and enforce explicit state transitions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, job_id: str) -> None:
        """Create one planned job."""
        now = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO jobs(job_id, state, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, JobState.PLANNED.value, now, now),
            )

    def get_state(self, job_id: str) -> JobState:
        """Return a job state or report a missing job."""
        row = self._connection.execute(
            "SELECT state FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            message = f"job not found: {job_id}"
            raise RecordNotFound(message)
        return JobState(row["state"])

    def transition(self, job_id: str, target: JobState) -> None:
        """Apply one allowed state transition."""
        current = self.get_state(job_id)
        if target not in ALLOWED_JOB_TRANSITIONS[current]:
            message = f"invalid job transition: {current.value} -> {target.value}"
            raise InvalidStateTransition(message)

        now = datetime.now(UTC).isoformat()
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE jobs
                SET state = ?, updated_at = ?
                WHERE job_id = ? AND state = ?
                """,
                (target.value, now, job_id, current.value),
            )
        if cursor.rowcount != 1:
            message = f"concurrent job transition: {job_id}"
            raise InvalidStateTransition(message)
