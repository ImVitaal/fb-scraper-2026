"""Acceptance tests for replay, required outputs, measurements, and retention."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.capture.rendered import RenderedPage
from app.retention import RetentionService
from app.session.profiles import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets.preparation import TargetPreparationService
from app.workflows.fixture_run import FixtureWorkflow
from app.workflows.html_replay import StoredHtmlReplayWorkflow
from app.workflows.live_capture import LiveCaptureWorkflow

FIXTURE = Path(__file__).parents[1] / "fixtures" / "one_group_capture.json"
HTML_FIXTURE = Path(__file__).parents[1] / "fixtures" / "live_group_pages" / "group.html"
EXPECTED_FIXTURE_IDS = {
    "comment:comment-fixture-3001",
    "group:group-fixture-1001",
    "post:post-fixture-2001",
}
EXPECTED_HTML_IDS = {"comment:comment-live", "group:group-live", "post:post-live"}


def _sqlite_identifiers(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            f"{entity_type}:{canonical_id}"
            for entity_type, canonical_id in connection.execute(
                "SELECT entity_type, canonical_id FROM records"
            )
        }


def _csv_identifiers(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as source:
        return {f"{row['entity_type']}:{row['canonical_id']}" for row in csv.DictReader(source)}


def test_fixture_outputs_and_measurement_receipts_share_identifiers(tmp_path: Path) -> None:
    output = tmp_path / "operator"
    workflow = FixtureWorkflow(output, tmp_path / "raw")

    run = workflow.run(FIXTURE)
    replay = workflow.replay(run.run_id)

    export_root = output / "exports"
    sqlite_export = export_root / f"{run.run_id}.sqlite3"
    assert _sqlite_identifiers(sqlite_export) == EXPECTED_FIXTURE_IDS
    assert _csv_identifiers(export_root / f"{run.run_id}.csv") == EXPECTED_FIXTURE_IDS
    assert (
        set(
            json.loads((export_root / f"{run.run_id}.json").read_text(encoding="utf-8"))[
                "identifiers"
            ]
        )
        == EXPECTED_FIXTURE_IDS
    )
    manifest = json.loads((export_root / f"{run.run_id}.manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["identifiers"]) == EXPECTED_FIXTURE_IDS
    assert manifest["files"]["sqlite"] == hashlib.sha256(sqlite_export.read_bytes()).hexdigest()
    assert replay.identifiers == run.identifiers
    for operation in ("run", "replay"):
        receipt = json.loads(
            (export_root / f"{run.run_id}.{operation}.metrics.json").read_text(encoding="utf-8")
        )
        assert receipt["operation"] == operation
        assert receipt["counts"]["groups"] == 1
        assert receipt["counts"]["posts"] == 1
        assert receipt["counts"]["comments"] == 1
        assert receipt["duration_seconds"] >= 0
        assert receipt["cpu_seconds"] >= 0
        assert receipt["peak_memory_bytes"] >= 0
        assert receipt["storage_delta_bytes"] >= 0


def test_manifest_hash_is_independent_of_operator_output_root(tmp_path: Path) -> None:
    first = FixtureWorkflow(tmp_path / "first-output", tmp_path / "first-raw").run(FIXTURE)
    second = FixtureWorkflow(tmp_path / "second-output", tmp_path / "second-raw").run(FIXTURE)

    first_manifest = (
        tmp_path / "first-output" / "exports" / f"{first.run_id}.manifest.json"
    ).read_bytes()
    second_manifest = (
        tmp_path / "second-output" / "exports" / f"{second.run_id}.manifest.json"
    ).read_bytes()

    assert first_manifest == second_manifest


def test_stored_html_replay_is_offline_and_exports_matching_identifiers(
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator"
    raw_root = tmp_path / "raw"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, tmp_path / "sessions").import_state(
            "profile-replay",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-live"
        )
        JobRepository(database.connection).create("job-replay")
        LiveRunRepository(database.connection).create(
            "job-replay",
            "profile-replay",
            selected,
            datetime(2026, 7, 1, tzinfo=UTC),
            "fixture/1.0",
        )
    first_page = HTML_FIXTURE.read_bytes()
    second_page = (
        HTML_FIXTURE.read_text(encoding="utf-8")
        .replace("post-live", "post-live-2")
        .replace("comment-live", "comment-live-2")
        .replace("reply-live", "reply-live-2")
        .replace("2026-07-29T12:00:00Z", "2026-07-29T12:01:00Z")
        .encode()
    )
    captured = LiveCaptureWorkflow(output, raw_root).capture_pages(
        "job-replay",
        lambda cursor: (
            RenderedPage(first_page, "page-2")
            if cursor is None
            else RenderedPage(second_page, None)
        ),
        max_pages=2,
    )

    replayed = StoredHtmlReplayWorkflow(output, raw_root).replay("job-replay", offline=True)
    export_root = output / "exports"
    first_hashes = {
        suffix: hashlib.sha256((export_root / f"job-replay.{suffix}").read_bytes()).hexdigest()
        for suffix in ("csv", "json", "md", "sqlite3", "manifest.json")
    }
    replayed_again = StoredHtmlReplayWorkflow(output, raw_root).replay("job-replay", offline=True)

    expected = EXPECTED_HTML_IDS | {"comment:comment-live-2", "post:post-live-2"}
    assert set(captured.identifiers) == expected
    assert set(replayed.identifiers) == expected
    assert replayed_again.normalized_sha256 == replayed.normalized_sha256
    assert {
        suffix: hashlib.sha256((export_root / f"job-replay.{suffix}").read_bytes()).hexdigest()
        for suffix in ("csv", "json", "md", "sqlite3", "manifest.json")
    } == first_hashes
    assert replayed.normalized_sha256
    assert _sqlite_identifiers(export_root / "job-replay.sqlite3") == expected
    assert _csv_identifiers(export_root / "job-replay.csv") == expected
    receipt = json.loads(
        (export_root / "job-replay.replay.metrics.json").read_text(encoding="utf-8")
    )
    assert receipt["counts"]["groups"] == 1
    assert receipt["counts"]["posts"] == 2
    assert receipt["counts"]["comments"] == 2


def test_retention_keeps_exact_boundaries_and_dry_run_changes_no_data(
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator"
    raw_root = tmp_path / "raw"
    result = FixtureWorkflow(output, raw_root).run(FIXTURE)
    now = datetime(2026, 7, 29, tzinfo=UTC)
    raw_boundary = now - timedelta(days=30)
    normalized_boundary = now - timedelta(days=90)
    database_path = output / "scanner.sqlite3"
    with Database(database_path) as database:
        with database.connection:
            database.connection.execute(
                "UPDATE raw_captures SET collected_at = ?", (raw_boundary.isoformat(),)
            )
            for table in ("groups", "posts", "comments"):
                database.connection.execute(
                    f"UPDATE {table} SET observed_at = ?",
                    (normalized_boundary.isoformat(),),
                )
        receipts = RetentionService(database.connection, raw_root).clean(
            raw_older_than="30d",
            normalized_older_than="90d",
            dry_run=True,
            now=now,
        )
        assert [receipt.deleted_count for receipt in receipts] == [0, 0]
        with database.connection:
            database.connection.execute(
                "UPDATE raw_captures SET collected_at = ?",
                ((raw_boundary - timedelta(microseconds=1)).isoformat(),),
            )
            for table in ("groups", "posts", "comments"):
                database.connection.execute(
                    f"UPDATE {table} SET observed_at = ?",
                    ((normalized_boundary - timedelta(microseconds=1)).isoformat(),),
                )
        dry_receipts = RetentionService(database.connection, raw_root).clean(
            raw_older_than="30d",
            normalized_older_than="90d",
            dry_run=True,
            now=now,
        )
        assert [receipt.deleted_count for receipt in dry_receipts] == [1, 3]
        counts = [
            database.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("groups", "posts", "comments")
        ]
    assert counts == [1, 1, 1]
    assert (raw_root / f"{result.run_id}.json.gz").is_file()
