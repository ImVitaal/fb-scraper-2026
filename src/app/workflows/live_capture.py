"""Raw-first, fixture-backed live capture for one selected Group."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.capture import GzipRawCaptureStore
from app.contracts.models import JobState
from app.parsing.live_group import LiveGroupParser
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import (
    CanonicalRepository,
    JobRepository,
    RawCaptureMetadataRepository,
)


@dataclass(frozen=True)
class LiveCaptureResult:
    """Stable evidence produced by a live HTML capture."""

    job_id: str
    identifiers: tuple[str, ...]
    state: JobState


class LiveCaptureWorkflow:
    """Persist raw HTML before parse, filter the run boundary, then checkpoint completion."""

    def __init__(self, output: Path, raw_root: Path) -> None:
        self.output = output
        self.raw_store = GzipRawCaptureStore(raw_root)

    def capture_html(self, job_id: str, raw_html: bytes) -> LiveCaptureResult:
        """Capture one supported Group page; repeated bytes remain idempotent."""
        with Database(self.output / "scanner.sqlite3") as database:
            database.migrate()
            live_run = LiveRunRepository(database.connection).get(job_id)
            jobs = JobRepository(database.connection)
            state = jobs.get_state(job_id)
            if state is JobState.PLANNED:
                jobs.transition(job_id, JobState.RUNNING)
            if jobs.get_state(job_id) is not JobState.RUNNING:
                raise ValueError(f"live capture job is not runnable: {job_id}")
            raw_sha256 = sha256(raw_html).hexdigest()
            capture_id = sha256(f"{job_id}|group-root|{raw_sha256}".encode()).hexdigest()
            stored = self.raw_store.write(capture_id, raw_html, suffix=".html")
            group, posts, comments = LiveGroupParser().parse(
                raw_html,
                source_url=live_run.canonical_url,
                capture_id=capture_id,
                raw_sha256=stored.sha256,
                session_class="fixture",
            )
            if group.group_id != live_run.group_id:
                raise ValueError("captured Group does not match selected target")
            captures = RawCaptureMetadataRepository(database.connection)
            captures.add(
                capture_id=capture_id,
                sha256=stored.sha256,
                source_url=live_run.canonical_url,
                collected_at=group.collected_at,
                storage_path=stored.path.name,
                byte_count=stored.byte_count,
            )
            records = CanonicalRepository(database.connection)
            records.save_group(group)
            selected_posts = [
                post
                for post in posts
                if post.published_at and post.published_at >= live_run.lower_bound
            ]
            for post in selected_posts:
                records.save_post(post)
            selected_ids = {post.post_id for post in selected_posts}
            for comment in comments:
                if comment.post_id in selected_ids:
                    records.save_comment(comment)
            with database.connection:
                database.connection.execute(
                    """
                    INSERT OR IGNORE INTO tasks(
                        task_id, job_id, idempotency_key, surface, state, created_at, updated_at
                    ) VALUES (?, ?, ?, 'group', 'succeeded', ?, ?)
                    """,
                    (
                        job_id,
                        job_id,
                        f"group:{job_id}",
                        group.collected_at.isoformat(),
                        group.collected_at.isoformat(),
                    ),
                )
                database.connection.execute(
                    """
                    INSERT OR IGNORE INTO pagination_checkpoints(
                        checkpoint_id, task_id, raw_capture_id, cursor,
                        interaction_number, durable_at
                    ) VALUES (?, ?, ?, NULL, 0, ?)
                    """,
                    (f"checkpoint:{job_id}", job_id, capture_id, group.collected_at.isoformat()),
                )
            jobs.transition(job_id, JobState.SUCCEEDED)
        identifiers = [f"group:{group.group_id}"]
        identifiers.extend(f"post:{post.post_id}" for post in selected_posts)
        identifiers.extend(
            f"comment:{comment.comment_id}"
            for comment in comments
            if comment.post_id in selected_ids
        )
        return LiveCaptureResult(job_id, tuple(sorted(identifiers)), JobState.SUCCEEDED)
