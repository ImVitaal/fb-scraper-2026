"""Offline replay of stored, integrity-checked Group HTML captures."""

from __future__ import annotations

from pathlib import Path

from app.capture import GzipRawCaptureStore, RawCaptureIntegrityError
from app.contracts.models import CommentRecord, GroupRecord, PostRecord
from app.parsing.live_group import LiveGroupParser
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.workflows.fixture_run import FixtureWorkflow, WorkflowResult


class StoredHtmlReplayWorkflow:
    """Rebuild canonical outputs only from durable HTML capture bytes."""

    def __init__(self, output: Path, raw_root: Path) -> None:
        self.output = output.resolve()
        self.raw_root = raw_root.resolve()
        self.database_path = self.output / "scanner.sqlite3"
        self.raw_store = GzipRawCaptureStore(self.raw_root)
        self.delivery = FixtureWorkflow(self.output, self.raw_root)

    def replay(self, job_id: str, *, offline: bool = True) -> WorkflowResult:
        """Verify and parse every checkpointed HTML page without network access."""
        if not offline:
            raise ValueError("stored HTML replay requires offline=True")
        timer = self.delivery._timer()
        timer.start()
        try:
            with Database(self.database_path) as database:
                database.migrate()
                live_run = LiveRunRepository(database.connection).get(job_id)
                pages = database.connection.execute(
                    """
                    SELECT
                        checkpoint.interaction_number,
                        capture.capture_id,
                        capture.sha256,
                        capture.storage_path,
                        capture.byte_count
                    FROM pagination_checkpoints AS checkpoint
                    JOIN tasks AS task ON task.task_id = checkpoint.task_id
                    JOIN raw_captures AS capture
                        ON capture.capture_id = checkpoint.raw_capture_id
                    WHERE task.job_id = ?
                    ORDER BY checkpoint.interaction_number, checkpoint.checkpoint_id
                    """,
                    (job_id,),
                ).fetchall()
            if not pages:
                raise RawCaptureIntegrityError(f"no checkpointed HTML captures: {job_id}")
            group: GroupRecord | None = None
            posts_by_id: dict[str, PostRecord] = {}
            comments_by_id: dict[str, CommentRecord] = {}
            parser = LiveGroupParser()
            for page in pages:
                capture_id = str(page["capture_id"])
                storage_path = str(page["storage_path"])
                if storage_path != f"{capture_id}.html.gz":
                    raise RawCaptureIntegrityError(
                        f"raw capture storage key is invalid: {capture_id}"
                    )
                raw_html = self.raw_store.read(capture_id, str(page["sha256"]), suffix=".html")
                if page["byte_count"] is not None and len(raw_html) != int(page["byte_count"]):
                    raise RawCaptureIntegrityError(f"raw capture byte count mismatch: {capture_id}")
                parsed_group, parsed_posts, parsed_comments = parser.parse(
                    raw_html,
                    source_url=live_run.canonical_url,
                    capture_id=capture_id,
                    raw_sha256=str(page["sha256"]),
                    session_class="fixture",
                )
                if parsed_group.group_id != live_run.group_id:
                    raise ValueError("replayed Group does not match selected target")
                if group is None:
                    group = parsed_group
                elif group.group_id != parsed_group.group_id:
                    raise ValueError("replayed pages contain multiple Groups")
                selected_posts = [
                    post
                    for post in parsed_posts
                    if post.published_at is not None and post.published_at >= live_run.lower_bound
                ]
                for post in selected_posts:
                    posts_by_id[post.post_id] = post
                selected_post_ids = set(posts_by_id)
                for comment in parsed_comments:
                    if comment.post_id in selected_post_ids:
                        comments_by_id[comment.comment_id] = comment
            if group is None:
                raise RawCaptureIntegrityError(f"no replayable Group capture: {job_id}")
            posts = sorted(posts_by_id.values(), key=lambda value: value.post_id)
            comments = sorted(comments_by_id.values(), key=lambda value: value.comment_id)
            result = self.delivery._export(job_id, group, posts, comments)
        except BaseException:
            timer.stop()
            raise
        measurement = timer.stop()
        self.delivery._write_measurement("replay", job_id, group, posts, comments, measurement)
        return result
