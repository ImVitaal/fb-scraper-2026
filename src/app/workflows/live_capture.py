"""Raw-first, resumable rendered capture for one selected Group."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.capture import GzipRawCaptureStore, RenderedPage, RenderedPageCapture
from app.capture.pagination import PageLimitExceeded, PaginationLoopError
from app.contracts.models import CommentRecord, GroupRecord, JobState, PostRecord
from app.metrics import (
    MeasurementCounts,
    MeasurementReceiptWriter,
    ProcessResourceMeasurement,
    ProcessResourceTimer,
    ResourceSnapshot,
    directory_storage_bytes,
    process_memory_bytes,
)
from app.parsing.live_group import LiveGroupParser, UnsupportedLayoutError
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import (
    CanonicalRepository,
    JobRepository,
    RawCaptureMetadataRepository,
)


@dataclass(frozen=True)
class LiveCaptureResult:
    """Stable evidence produced by a rendered capture."""

    job_id: str
    identifiers: tuple[str, ...]
    state: JobState


class LiveCaptureWorkflow:
    """Persist and parse bounded rendered pages with durable resume cursors."""

    def __init__(self, output: Path, raw_root: Path) -> None:
        self.output = output
        self.raw_store = GzipRawCaptureStore(raw_root)

    def capture_html(
        self, job_id: str, raw_html: bytes, *, interrupt_after_checkpoint: bool = False
    ) -> LiveCaptureResult:
        """Capture one rendered page through the resumable page workflow."""
        return self.capture_pages(
            job_id,
            lambda cursor: RenderedPage(raw_html, None),
            max_pages=1,
            interrupt_after_pages=1 if interrupt_after_checkpoint else None,
        )

    def capture_pages(
        self,
        job_id: str,
        capture_page: RenderedPageCapture,
        *,
        max_pages: int,
        interrupt_after_pages: int | None = None,
    ) -> LiveCaptureResult:
        """Capture rendered pages and write one successful run or resume receipt."""
        operation = self._measurement_operation(job_id)
        timer = self._timer()
        timer.start()
        try:
            result = self._capture_pages(
                job_id,
                capture_page,
                max_pages=max_pages,
                interrupt_after_pages=interrupt_after_pages,
            )
        except BaseException:
            timer.stop()
            raise
        measurement = timer.stop()
        self._write_measurement(operation, job_id, measurement)
        return result

    def _capture_pages(
        self,
        job_id: str,
        capture_page: RenderedPageCapture,
        *,
        max_pages: int,
        interrupt_after_pages: int | None,
    ) -> LiveCaptureResult:
        """Run the raw-first durable capture loop."""
        if max_pages <= 0:
            raise ValueError("max_pages must be greater than zero")
        if interrupt_after_pages is not None and interrupt_after_pages <= 0:
            raise ValueError("interrupt_after_pages must be greater than zero")

        with Database(self.output / "scanner.sqlite3") as database:
            database.migrate()
            live_run = LiveRunRepository(database.connection).get(job_id)
            jobs = JobRepository(database.connection)
            state = jobs.get_state(job_id)
            if state in {JobState.PLANNED, JobState.INTERRUPTED, JobState.PARTIAL}:
                jobs.transition(job_id, JobState.RUNNING)
            if jobs.get_state(job_id) is not JobState.RUNNING:
                raise ValueError(f"live capture job is not runnable: {job_id}")

            self._ensure_task(database.connection, job_id)
            cursor, pages_completed, seen_cursors = self._resume_position(
                database.connection, job_id
            )
            pages_this_attempt = 0

            while True:
                page_number = pages_completed + 1
                page = capture_page(cursor)
                pages_this_attempt += 1
                raw_digest = sha256(page.raw_html).hexdigest()
                cursor_key = cursor if cursor is not None else "group-root"
                capture_id = sha256(
                    f"{job_id}|{page_number}|{cursor_key}|{raw_digest}".encode()
                ).hexdigest()

                # The raw file becomes durable before any parser sees the bytes.
                stored = self.raw_store.write(capture_id, page.raw_html, suffix=".html")
                try:
                    group, posts, comments = LiveGroupParser().parse(
                        page.raw_html,
                        source_url=live_run.canonical_url,
                        capture_id=capture_id,
                        raw_sha256=stored.sha256,
                        session_class="fixture",
                    )
                except UnsupportedLayoutError as error:
                    self._record_failure(
                        database,
                        jobs,
                        job_id,
                        capture_id,
                        "parser_drift",
                        str(error),
                    )
                    raise

                if group.group_id != live_run.group_id:
                    error = UnsupportedLayoutError("captured Group does not match selected target")
                    self._record_failure(
                        database,
                        jobs,
                        job_id,
                        capture_id,
                        "parser_drift",
                        str(error),
                    )
                    raise error

                self._persist_page(
                    database,
                    live_run.canonical_url,
                    live_run.lower_bound,
                    stored.path.name,
                    stored.byte_count,
                    group,
                    posts,
                    comments,
                )

                next_cursor = page.next_cursor
                if next_cursor is None:
                    self._checkpoint(
                        database.connection,
                        job_id,
                        capture_id,
                        None,
                        page_number,
                    )
                    if (
                        interrupt_after_pages is not None
                        and pages_this_attempt >= interrupt_after_pages
                    ):
                        self._set_task_state(database.connection, job_id, "interrupted")
                        jobs.transition(job_id, JobState.INTERRUPTED)
                        raise KeyboardInterrupt
                    self._set_task_state(database.connection, job_id, "succeeded")
                    jobs.transition(job_id, JobState.SUCCEEDED)
                    return LiveCaptureResult(
                        job_id,
                        self._identifiers(database.connection, live_run.group_id),
                        JobState.SUCCEEDED,
                    )

                if page_number >= max_pages:
                    error = PageLimitExceeded(f"pagination exceeded max_pages={max_pages}")
                    self._record_failure(
                        database,
                        jobs,
                        job_id,
                        capture_id,
                        "page_limit",
                        str(error),
                    )
                    raise error
                if next_cursor in seen_cursors:
                    error = PaginationLoopError(f"repeated pagination cursor: {next_cursor!r}")
                    self._record_failure(
                        database,
                        jobs,
                        job_id,
                        capture_id,
                        "pagination_loop",
                        str(error),
                    )
                    raise error

                self._checkpoint(
                    database.connection,
                    job_id,
                    capture_id,
                    next_cursor,
                    page_number,
                )
                if (
                    interrupt_after_pages is not None
                    and pages_this_attempt >= interrupt_after_pages
                ):
                    self._set_task_state(database.connection, job_id, "interrupted")
                    jobs.transition(job_id, JobState.INTERRUPTED)
                    raise KeyboardInterrupt

                seen_cursors.add(next_cursor)
                cursor = next_cursor
                pages_completed = page_number

    def _measurement_operation(self, job_id: str) -> str:
        with Database(self.output / "scanner.sqlite3") as database:
            state = JobRepository(database.connection).get_state(job_id)
        return "resume" if state is JobState.INTERRUPTED else "run"

    def _timer(self) -> ProcessResourceTimer:
        def snapshot() -> ResourceSnapshot:
            return ResourceSnapshot(
                memory_bytes=process_memory_bytes(),
                storage_bytes=directory_storage_bytes(self.output)
                + directory_storage_bytes(self.raw_store.root),
            )

        return ProcessResourceTimer(resource_snapshot=snapshot)

    def _write_measurement(
        self,
        operation: str,
        job_id: str,
        measurement: ProcessResourceMeasurement,
    ) -> None:
        with Database(self.output / "scanner.sqlite3") as database:
            live_run = LiveRunRepository(database.connection).get(job_id)
            posts = database.connection.execute(
                "SELECT COUNT(*) AS count FROM posts WHERE group_id = ?",
                (live_run.group_id,),
            ).fetchone()
            comments = database.connection.execute(
                "SELECT COUNT(*) AS count FROM comments WHERE group_id = ?",
                (live_run.group_id,),
            ).fetchone()
            attempts = database.connection.execute(
                "SELECT COUNT(*) AS count FROM attempts WHERE task_id = ?",
                (job_id,),
            ).fetchone()
            failures = database.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM failures
                WHERE attempt_id IN (
                    SELECT attempt_id FROM attempts WHERE task_id = ?
                )
                """,
                (job_id,),
            ).fetchone()
        attempt_count = int(attempts["count"])
        MeasurementReceiptWriter(self.output / "exports").write(
            operation=operation,
            run_id=job_id,
            counts=MeasurementCounts(
                groups=1,
                posts=int(posts["count"]),
                comments=int(comments["count"]),
                retries=int(operation == "resume") + max(0, attempt_count - 1),
                failures=int(failures["count"]),
            ),
            measurement=measurement,
            completeness=1.0,
        )

    @staticmethod
    def _ensure_task(connection: sqlite3.Connection, job_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO tasks(
                    task_id, job_id, idempotency_key, surface, state, created_at, updated_at
                ) VALUES (?, ?, ?, 'group', 'running', ?, ?)
                """,
                (job_id, job_id, f"group:{job_id}", now, now),
            )
            connection.execute(
                "UPDATE tasks SET state = 'running', updated_at = ? WHERE task_id = ?",
                (now, job_id),
            )

    @staticmethod
    def _set_task_state(connection: sqlite3.Connection, job_id: str, state: str) -> None:
        with connection:
            connection.execute(
                "UPDATE tasks SET state = ?, updated_at = ? WHERE task_id = ?",
                (state, datetime.now(UTC).isoformat(), job_id),
            )

    @staticmethod
    def _resume_position(
        connection: sqlite3.Connection, job_id: str
    ) -> tuple[str | None, int, set[str]]:
        rows = connection.execute(
            """
            SELECT cursor, interaction_number
            FROM pagination_checkpoints
            WHERE task_id = ?
            ORDER BY interaction_number
            """,
            (job_id,),
        ).fetchall()
        non_terminal = [row for row in rows if row["cursor"] is not None]
        if not non_terminal:
            return None, 0, set()
        latest = non_terminal[-1]
        return (
            str(latest["cursor"]),
            int(latest["interaction_number"]),
            {str(row["cursor"]) for row in non_terminal},
        )

    @staticmethod
    def _checkpoint(
        connection: sqlite3.Connection,
        job_id: str,
        capture_id: str,
        cursor: str | None,
        interaction_number: int,
    ) -> None:
        checkpoint_id = sha256(
            f"{job_id}|{interaction_number}|{cursor or 'terminal'}".encode()
        ).hexdigest()
        durable_at = datetime.now(UTC).isoformat()
        with connection:
            connection.execute(
                """
                INSERT INTO pagination_checkpoints(
                    checkpoint_id, task_id, raw_capture_id, cursor,
                    interaction_number, durable_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, interaction_number) DO UPDATE SET
                    checkpoint_id = excluded.checkpoint_id,
                    raw_capture_id = excluded.raw_capture_id,
                    cursor = excluded.cursor,
                    durable_at = excluded.durable_at
                """,
                (
                    checkpoint_id,
                    job_id,
                    capture_id,
                    cursor,
                    interaction_number,
                    durable_at,
                ),
            )

    @staticmethod
    def _persist_page(
        database: Database,
        source_url: str,
        lower_bound: datetime,
        storage_path: str,
        byte_count: int,
        group: GroupRecord,
        posts: list[PostRecord],
        comments: list[CommentRecord],
    ) -> None:
        captures = RawCaptureMetadataRepository(database.connection)
        captures.add(
            capture_id=group.raw_capture_id,
            sha256=group.raw_sha256,
            source_url=source_url,
            collected_at=group.collected_at,
            storage_path=storage_path,
            byte_count=byte_count,
        )
        records = CanonicalRepository(database.connection)
        records.save_group(group)
        selected_posts = [
            post
            for post in posts
            if post.published_at is not None and post.published_at >= lower_bound
        ]
        for post in selected_posts:
            records.save_post(post)
        selected_ids = {post.post_id for post in selected_posts}
        for comment in comments:
            if comment.post_id in selected_ids:
                records.save_comment(comment)

    @staticmethod
    def _identifiers(connection: sqlite3.Connection, group_id: str) -> tuple[str, ...]:
        identifiers = [f"group:{group_id}"]
        identifiers.extend(
            f"post:{row['post_id']}"
            for row in connection.execute(
                "SELECT post_id FROM posts WHERE group_id = ?", (group_id,)
            )
        )
        identifiers.extend(
            f"comment:{row['comment_id']}"
            for row in connection.execute(
                "SELECT comment_id FROM comments WHERE group_id = ?", (group_id,)
            )
        )
        return tuple(sorted(identifiers))

    @classmethod
    def _record_failure(
        cls,
        database: Database,
        jobs: JobRepository,
        job_id: str,
        capture_id: str,
        failure_class: str,
        message: str,
    ) -> None:
        recorded_at = datetime.now(UTC).isoformat()
        row = database.connection.execute(
            "SELECT COALESCE(MAX(attempt_number), 0) AS value FROM attempts WHERE task_id = ?",
            (job_id,),
        ).fetchone()
        attempt_number = int(row["value"]) + 1
        attempt_id = f"attempt:{job_id}:{attempt_number}"
        health = failure_class if failure_class == "parser_drift" else "partial"
        with database.connection:
            database.connection.execute(
                """
                INSERT INTO attempts(
                    attempt_id, task_id, attempt_number, health, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    job_id,
                    attempt_number,
                    health,
                    recorded_at,
                    recorded_at,
                ),
            )
            database.connection.execute(
                """
                INSERT INTO failures(
                    failure_id, attempt_id, failure_class, message, recorded_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"failure:{job_id}:{attempt_number}",
                    attempt_id,
                    failure_class,
                    f"{capture_id}: {message}",
                    recorded_at,
                ),
            )
        cls._set_task_state(database.connection, job_id, "failed")
        if jobs.get_state(job_id) is JobState.RUNNING:
            jobs.transition(job_id, JobState.FAILED)
