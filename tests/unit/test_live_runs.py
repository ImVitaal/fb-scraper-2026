"""Tests for durable live capture run context."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.session.profiles import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets.preparation import TargetPreparationService


def test_live_run_persists_selected_target_and_boundary(tmp_path: Path) -> None:
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, tmp_path / "sessions").import_state(
            "profile-live",
            {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-live"
        )
        JobRepository(database.connection).create("job-live")
        lower_bound = datetime(2026, 7, 1, tzinfo=UTC)
        runs = LiveRunRepository(database.connection)
        runs.create("job-live", "profile-live", selected, lower_bound, "playwright_group/1.0")

        restored = runs.get("job-live")

    assert restored.job_id == "job-live"
    assert restored.group_id == "group-live"
    assert restored.lower_bound == lower_bound
