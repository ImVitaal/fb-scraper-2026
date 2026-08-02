"""Acceptance tests for multi-page capture and durable resume."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.capture.pagination import PageLimitExceeded, PaginationLoopError
from app.capture.rendered import RenderedPage
from app.contracts.models import JobState
from app.session.profiles import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets.preparation import TargetPreparationService
from app.workflows.live_capture import LiveCaptureWorkflow

FIXTURE = Path(__file__).parents[1] / "fixtures" / "live_group_pages" / "group.html"


def _html(post_id: str, comment_id: str, *, observed_at: str) -> bytes:
    raw = FIXTURE.read_text(encoding="utf-8")
    return (
        raw.replace("post-live", post_id)
        .replace("comment-live", comment_id)
        .replace("reply-live", f"reply-{post_id}")
        .replace("2026-07-29T12:00:00Z", observed_at)
        .encode()
    )


def _prepare(output: Path, session_root: Path, job_id: str) -> None:
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            f"profile-{job_id}",
            {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-live"
        )
        JobRepository(database.connection).create(job_id)
        LiveRunRepository(database.connection).create(
            job_id,
            f"profile-{job_id}",
            selected,
            datetime(2026, 7, 1, tzinfo=UTC),
            "synthetic-rendered/1.0",
        )


def _source(
    pages: dict[str | None, RenderedPage],
    events: list[str],
    before_fetch: Callable[[str | None], None] | None = None,
) -> Callable[[str | None], RenderedPage]:
    def capture(cursor: str | None) -> RenderedPage:
        if before_fetch is not None:
            before_fetch(cursor)
        events.append(f"fetch:{cursor}")
        return pages[cursor]

    return capture


def test_multi_page_capture_checkpoints_before_next_fetch_and_stores_every_raw_page(
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "raw"
    _prepare(output, tmp_path / "sessions", "job-pages")
    pages = {
        None: RenderedPage(
            _html("post-one", "comment-one", observed_at="2026-07-29T12:00:00Z"), "p2"
        ),
        "p2": RenderedPage(
            _html("post-two", "comment-two", observed_at="2026-07-29T12:01:00Z"),
            None,
        ),
    }
    events: list[str] = []

    def require_durable_checkpoint(cursor: str | None) -> None:
        if cursor != "p2":
            return
        with Database(output / "scanner.sqlite3") as database:
            row = database.connection.execute(
                """
                SELECT cursor FROM pagination_checkpoints
                WHERE task_id = ? ORDER BY interaction_number DESC LIMIT 1
                """,
                ("job-pages",),
            ).fetchone()
        assert row is not None
        assert row["cursor"] == "p2"

    result = LiveCaptureWorkflow(output, raw_root).capture_pages(
        "job-pages",
        _source(pages, events, require_durable_checkpoint),
        max_pages=2,
    )

    assert result.identifiers == (
        "comment:comment-one",
        "comment:comment-two",
        "group:group-live",
        "post:post-one",
        "post:post-two",
    )
    assert events == ["fetch:None", "fetch:p2"]
    assert len(list(raw_root.glob("*.html.gz"))) == 2
    receipt = json.loads(
        (output / "exports" / "job-pages.run.metrics.json").read_text(encoding="utf-8")
    )
    assert receipt["operation"] == "run"
    assert receipt["counts"] == {
        "comments": 2,
        "failures": 0,
        "groups": 1,
        "posts": 2,
        "retries": 0,
    }
    assert receipt["completeness"] == 1.0
    assert receipt["duration_seconds"] >= 0
    assert receipt["cpu_seconds"] >= 0
    assert receipt["peak_memory_bytes"] >= 0
    assert receipt["storage_delta_bytes"] >= 0


def test_interruption_resumes_from_checkpoint_with_identical_identifiers(tmp_path: Path) -> None:
    pages = {
        None: RenderedPage(
            _html("post-one", "comment-one", observed_at="2026-07-29T12:00:00Z"), "p2"
        ),
        "p2": RenderedPage(
            _html("post-two", "comment-two", observed_at="2026-07-29T12:01:00Z"),
            None,
        ),
    }
    uninterrupted_output = tmp_path / "uninterrupted"
    resumed_output = tmp_path / "resumed"
    _prepare(uninterrupted_output, tmp_path / "sessions-a", "job-uninterrupted")
    _prepare(resumed_output, tmp_path / "sessions-b", "job-resumed")

    uninterrupted = LiveCaptureWorkflow(uninterrupted_output, tmp_path / "raw-a").capture_pages(
        "job-uninterrupted",
        _source(pages, []),
        max_pages=2,
    )
    first_events: list[str] = []
    resumed_workflow = LiveCaptureWorkflow(resumed_output, tmp_path / "raw-b")
    with pytest.raises(KeyboardInterrupt):
        resumed_workflow.capture_pages(
            "job-resumed",
            _source(pages, first_events),
            max_pages=2,
            interrupt_after_pages=1,
        )
    assert not (resumed_output / "exports" / "job-resumed.run.metrics.json").exists()
    resumed_events: list[str] = []
    resumed = resumed_workflow.capture_pages(
        "job-resumed",
        _source(pages, resumed_events),
        max_pages=2,
    )

    assert first_events == ["fetch:None"]
    assert resumed_events == ["fetch:p2"]
    assert resumed.identifiers == uninterrupted.identifiers
    receipt = json.loads(
        (resumed_output / "exports" / "job-resumed.resume.metrics.json").read_text(encoding="utf-8")
    )
    assert receipt["operation"] == "resume"
    assert receipt["counts"] == {
        "comments": 2,
        "failures": 0,
        "groups": 1,
        "posts": 2,
        "retries": 1,
    }
    assert receipt["completeness"] == 1.0
    assert receipt["duration_seconds"] >= 0
    assert receipt["cpu_seconds"] >= 0
    assert receipt["peak_memory_bytes"] >= 0
    assert receipt["storage_delta_bytes"] >= 0


@pytest.mark.parametrize(
    ("pages", "max_pages", "error_type", "failure_class"),
    [
        (
            {
                None: RenderedPage(
                    _html("post-one", "comment-one", observed_at="2026-07-29T12:00:00Z"),
                    "loop",
                ),
                "loop": RenderedPage(
                    _html("post-two", "comment-two", observed_at="2026-07-29T12:01:00Z"),
                    "loop",
                ),
            },
            3,
            PaginationLoopError,
            "pagination_loop",
        ),
        (
            {
                None: RenderedPage(
                    _html("post-one", "comment-one", observed_at="2026-07-29T12:00:00Z"),
                    "p2",
                )
            },
            1,
            PageLimitExceeded,
            "page_limit",
        ),
    ],
)
def test_pagination_failures_never_report_success(
    tmp_path: Path,
    pages: dict[str | None, RenderedPage],
    max_pages: int,
    error_type: type[Exception],
    failure_class: str,
) -> None:
    output = tmp_path / failure_class
    job_id = f"job-{failure_class}"
    _prepare(output, tmp_path / f"sessions-{failure_class}", job_id)

    with pytest.raises(error_type):
        LiveCaptureWorkflow(output, tmp_path / f"raw-{failure_class}").capture_pages(
            job_id,
            _source(pages, []),
            max_pages=max_pages,
        )

    with Database(output / "scanner.sqlite3") as database:
        state = JobRepository(database.connection).get_state(job_id)
        failure = database.connection.execute(
            "SELECT failure_class FROM failures ORDER BY recorded_at DESC LIMIT 1"
        ).fetchone()
    assert state is JobState.FAILED
    assert failure["failure_class"] == failure_class


def test_layout_drift_preserves_raw_and_records_non_success_health(tmp_path: Path) -> None:
    output = tmp_path / "drift"
    raw_root = tmp_path / "raw-drift"
    _prepare(output, tmp_path / "sessions-drift", "job-drift-lane")

    with pytest.raises(ValueError, match="group"):
        LiveCaptureWorkflow(output, raw_root).capture_pages(
            "job-drift-lane",
            lambda cursor: RenderedPage(b"<main>layout changed</main>", None),
            max_pages=1,
        )

    assert len(list(raw_root.glob("*.html.gz"))) == 1
    with Database(output / "scanner.sqlite3") as database:
        state = JobRepository(database.connection).get_state("job-drift-lane")
        attempt = database.connection.execute(
            "SELECT health FROM attempts WHERE task_id = ?", ("job-drift-lane",)
        ).fetchone()
        raw_capture = database.connection.execute(
            "SELECT storage_path, byte_count FROM raw_captures"
        ).fetchone()
    assert state is JobState.FAILED
    assert attempt["health"] == "parser_drift"
    assert raw_capture["storage_path"].endswith(".html.gz")
    assert raw_capture["byte_count"] > 0


def test_terminal_checkpoint_resume_finishes_without_refetching_the_page(
    tmp_path: Path,
) -> None:
    output = tmp_path / "terminal-resume"
    raw_root = tmp_path / "raw-terminal-resume"
    _prepare(output, tmp_path / "sessions-terminal-resume", "job-terminal-resume")
    page = RenderedPage(
        _html("post-terminal", "comment-terminal", observed_at="2026-07-29T12:00:00Z"), None
    )
    first_events: list[str] = []
    workflow = LiveCaptureWorkflow(output, raw_root)

    with pytest.raises(KeyboardInterrupt):
        workflow.capture_pages(
            "job-terminal-resume",
            _source({None: page}, first_events),
            max_pages=1,
            interrupt_after_pages=1,
        )

    resumed_events: list[str] = []
    result = workflow.capture_pages(
        "job-terminal-resume",
        _source({None: page}, resumed_events),
        max_pages=1,
    )

    assert first_events == ["fetch:None"]
    assert resumed_events == []
    assert result.state is JobState.SUCCEEDED
