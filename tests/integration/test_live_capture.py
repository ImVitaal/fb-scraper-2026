"""Synthetic live capture workflow acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.contracts.models import JobState
from app.parsing.live_group import UnsupportedLayoutError
from app.session.profiles import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets.preparation import TargetPreparationService
from app.workflows.live_capture import LiveCaptureWorkflow

FIXTURE = Path(__file__).parents[1] / "fixtures" / "live_group_pages" / "group.html"


def test_live_capture_stores_raw_before_parsing_and_filters_boundary(tmp_path: Path) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "raw"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, tmp_path / "sessions").import_state(
            "profile-live",
            {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-live"
        )
        JobRepository(database.connection).create("job-live")
        LiveRunRepository(database.connection).create(
            "job-live", "profile-live", selected, datetime(2026, 7, 1, tzinfo=UTC), "fixture/1.0"
        )

    result = LiveCaptureWorkflow(output, raw_root).capture_html("job-live", FIXTURE.read_bytes())

    assert result.identifiers == (
        "comment:comment-live",
        "group:group-live",
        "post:post-live",
    )
    assert list(raw_root.glob("*.html.gz"))


def test_live_capture_resume_after_checkpoint_preserves_identifiers(tmp_path: Path) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "raw"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, tmp_path / "sessions").import_state(
            "profile-resume",
            {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-live"
        )
        JobRepository(database.connection).create("job-resume")
        LiveRunRepository(database.connection).create(
            "job-resume",
            "profile-resume",
            selected,
            datetime(2026, 7, 1, tzinfo=UTC),
            "fixture/1.0",
        )

    workflow = LiveCaptureWorkflow(output, raw_root)
    with pytest.raises(KeyboardInterrupt):
        workflow.capture_html("job-resume", FIXTURE.read_bytes(), interrupt_after_checkpoint=True)
    resumed = workflow.capture_html("job-resume", FIXTURE.read_bytes())

    assert resumed.identifiers == (
        "comment:comment-live",
        "group:group-live",
        "post:post-live",
    )


def test_unsupported_live_layout_records_parser_drift_and_never_succeeds(tmp_path: Path) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "raw"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, tmp_path / "sessions").import_state(
            "profile-drift",
            {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-live"
        )
        JobRepository(database.connection).create("job-drift")
        LiveRunRepository(database.connection).create(
            "job-drift", "profile-drift", selected, datetime(2026, 7, 1, tzinfo=UTC), "fixture/1.0"
        )

    with pytest.raises(UnsupportedLayoutError, match="group"):
        LiveCaptureWorkflow(output, raw_root).capture_html("job-drift", b"<main>drift</main>")

    assert list(raw_root.glob("*.html.gz"))
    with Database(output / "scanner.sqlite3") as database:
        assert JobRepository(database.connection).get_state("job-drift") is JobState.FAILED
        attempt = database.connection.execute(
            "SELECT health FROM attempts WHERE task_id = ?", ("job-drift",)
        ).fetchone()
        failure = database.connection.execute(
            "SELECT failure_class FROM failures WHERE attempt_id = ?", ("attempt:job-drift:1",)
        ).fetchone()
    assert attempt["health"] == "parser_drift"
    assert failure["failure_class"] == "parser_drift"
