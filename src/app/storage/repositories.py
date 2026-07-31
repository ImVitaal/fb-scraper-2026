"""Repositories for Phase 1 canonical records and durable state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from re import fullmatch

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


class StaleObservation(RepositoryError):
    """Raised when older data would replace the current canonical record."""


class CanonicalIdentityConflict(RepositoryError):
    """Raised when an existing canonical identifier changes parent identity."""


class ObservationConflict(RepositoryError):
    """Raised when one timestamp has conflicting canonical payloads."""


class CounterObservationConflict(RepositoryError):
    """Raised when one counter observation key has conflicting evidence."""


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
    if value.tzinfo is None or value.utcoffset() is None:
        message = "timestamp must be timezone-aware"
        raise RepositoryError(message)
    return value.astimezone(UTC).isoformat()


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
        storage_path: str | None = None,
        byte_count: int | None = None,
    ) -> None:
        """Insert capture metadata or verify the existing immutable record."""
        normalized_sha256 = sha256.lower()
        if not capture_id:
            message = "capture_id must be non-empty"
            raise CaptureMetadataConflict(message)
        if fullmatch(r"[0-9a-f]{64}", normalized_sha256) is None:
            message = "sha256 must contain 64 hexadecimal characters"
            raise CaptureMetadataConflict(message)

        if byte_count is not None and byte_count < 0:
            message = "byte_count must be non-negative"
            raise CaptureMetadataConflict(message)
        expected = (normalized_sha256, source_url)
        normalized_collected_at = _timestamp(collected_at)
        with self._connection:
            row = self._connection.execute(
                """
                SELECT sha256, source_url, collected_at, storage_path, byte_count
                FROM raw_captures
                WHERE capture_id = ?
                """,
                (capture_id,),
            ).fetchone()
            if row is None:
                try:
                    self._connection.execute(
                        """
                        INSERT INTO raw_captures(
                            capture_id, sha256, source_url, collected_at, storage_path, byte_count
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (capture_id, *expected, normalized_collected_at, storage_path, byte_count),
                    )
                except sqlite3.IntegrityError as error:
                    message = f"invalid capture metadata: {capture_id}"
                    raise CaptureMetadataConflict(message) from error
            else:
                actual = (row["sha256"], row["source_url"])
                if actual != expected:
                    message = f"capture metadata conflict: {capture_id}"
                    raise CaptureMetadataConflict(message)
                location = (row["storage_path"], row["byte_count"])
                requested_location = (storage_path, byte_count)
                if requested_location != (None, None) and location != requested_location:
                    message = f"capture storage conflict: {capture_id}"
                    raise CaptureMetadataConflict(message)

    def get(self, capture_id: str) -> sqlite3.Row:
        """Return immutable capture metadata required for offline replay."""
        row = self._connection.execute(
            """
            SELECT capture_id, sha256, source_url, collected_at, storage_path, byte_count
            FROM raw_captures
            WHERE capture_id = ?
            """,
            (capture_id,),
        ).fetchone()
        if row is None:
            message = f"raw capture not found: {capture_id}"
            raise RecordNotFound(message)
        return row


class CanonicalRepository:
    """Persist versioned canonical records and immutable counter observations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save_group(self, record: GroupRecord) -> None:
        """Upsert the current Group record and append its counter observation."""
        payload = record.model_dump_json()
        with self._connection:
            self._guard_current_record(
                table="groups",
                id_column="group_id",
                record_id=record.group_id,
                observed_at=record.observed_at,
                payload_json=payload,
            )
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
                self._save_counter(
                    "group",
                    record.group_id,
                    "member_count",
                    record.observed_at,
                    record.member_count,
                    record.raw_capture_id,
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
        payload = record.model_dump_json()
        with self._connection:
            self._guard_current_record(
                table="posts",
                id_column="post_id",
                record_id=record.post_id,
                observed_at=record.observed_at,
                payload_json=payload,
                identity={"group_id": record.group_id},
            )
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
                    payload,
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
        payload = record.model_dump_json()
        with self._connection:
            self._guard_current_record(
                table="comments",
                id_column="comment_id",
                record_id=record.comment_id,
                observed_at=record.observed_at,
                payload_json=payload,
                identity={"post_id": record.post_id, "group_id": record.group_id},
            )
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
                    payload,
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
        observed_timestamp = _timestamp(observed_at)
        row = self._connection.execute(
            """
            SELECT value, raw_capture_id
            FROM counter_observations
            WHERE entity_type = ? AND entity_id = ? AND metric = ? AND observed_at = ?
            """,
            (
                entity_type,
                entity_id,
                metric,
                observed_timestamp,
            ),
        ).fetchone()
        if row is not None:
            if (row["value"], row["raw_capture_id"]) != (value, raw_capture_id):
                message = (
                    f"counter observation conflict: "
                    f"{entity_type}/{entity_id}/{metric}/{observed_timestamp}"
                )
                raise CounterObservationConflict(message)
            return

        self._connection.execute(
            """
            INSERT INTO counter_observations(
                entity_type, entity_id, metric, observed_at, value, raw_capture_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_type, entity_id, metric, observed_timestamp, value, raw_capture_id),
        )

    def _guard_current_record(
        self,
        *,
        table: str,
        id_column: str,
        record_id: str,
        observed_at: datetime,
        payload_json: str,
        identity: dict[str, str] | None = None,
    ) -> None:
        identity = identity or {}
        selected_columns = ["observed_at", "payload_json", *identity]
        row = self._connection.execute(
            f"SELECT {', '.join(selected_columns)} FROM {table} WHERE {id_column} = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            return

        for column, expected in identity.items():
            if row[column] != expected:
                message = f"canonical identity conflict: {table}/{record_id}/{column}"
                raise CanonicalIdentityConflict(message)

        current_time = datetime.fromisoformat(row["observed_at"])
        if observed_at < current_time:
            message = f"stale observation: {table}/{record_id}"
            raise StaleObservation(message)
        if observed_at == current_time and row["payload_json"] != payload_json:
            message = f"observation conflict: {table}/{record_id}/{_timestamp(observed_at)}"
            raise ObservationConflict(message)


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
