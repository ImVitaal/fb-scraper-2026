"""Deterministic runtime coverage for the Phase 4F one-Group gate."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.cli import main
from app.configuration import OperatorProtectionConfiguration
from app.session import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets import TargetPreparationService


def test_operator_capture_gate_rejects_a_second_active_group(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    lock = output / ".operator-capture.lock"
    lock.write_text("fixture-owner", encoding="ascii")

    with (
        pytest.raises(RuntimeError, match="another operator Group capture is active"),
        main._operator_capture_gate(
            output,
            "group-2",
            OperatorProtectionConfiguration(),
        ),
    ):
        pytest.fail("exclusive gate admitted a second Group")

    assert lock.read_text(encoding="ascii") == "fixture-owner"


def test_operator_gate_applies_900_second_inter_group_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    session_root = tmp_path / "sessions"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "fixture-profile",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/group-1"
        )
        JobRepository(database.connection).create("previous-run")
        LiveRunRepository(database.connection).create(
            "previous-run",
            "fixture-profile",
            selected,
            datetime(2026, 7, 30, 11, 0, tzinfo=UTC),
            "app_rendered_html/1.0",
        )
        jobs = JobRepository(database.connection)
        jobs.transition("previous-run", main.JobState.RUNNING)
        jobs.transition("previous-run", main.JobState.SUCCEEDED)
        database.connection.execute(
            "UPDATE jobs SET updated_at = ? WHERE job_id = ?",
            ("2026-07-30T12:00:00+00:00", "previous-run"),
        )
        database.connection.commit()

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 30, 12, 0, tzinfo=UTC)

    waits: list[float] = []
    monkeypatch.setattr(main, "datetime", _FrozenDateTime)
    monkeypatch.setattr(main.time, "sleep", waits.append)

    with main._operator_capture_gate(
        output,
        "group-2",
        OperatorProtectionConfiguration(),
    ) as applied:
        assert applied == 900.0

    assert waits == [900.0]
    assert not (output / ".operator-capture.lock").exists()
