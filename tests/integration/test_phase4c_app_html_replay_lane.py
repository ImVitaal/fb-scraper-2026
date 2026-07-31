"""Phase 4C offline replay tests for versioned APP HTML."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.capture import GzipRawCaptureStore, RawCaptureIntegrityError
from app.session.profiles import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository, RawCaptureMetadataRepository
from app.targets.preparation import TargetPreparationService
from app.workflows.html_replay import StoredHtmlReplayWorkflow

FIXTURE = Path(__file__).parents[1] / "fixtures" / "app_operator_redacted" / "group_page.html"


def test_stored_html_replay_requires_offline_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="offline=True"):
        StoredHtmlReplayWorkflow(tmp_path / "operator", tmp_path / "raw").replay(
            "job-online",
            offline=False,
        )


def test_stored_app_html_replay_uses_versioned_parser_and_actual_session_class(
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator"
    raw_root = tmp_path / "raw"
    observed_at = datetime(2026, 7, 30, tzinfo=UTC)
    capture_id = "capture-phase4c-replay"
    stored = GzipRawCaptureStore(raw_root).write(
        capture_id,
        FIXTURE.read_bytes(),
        suffix=".html",
    )
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, tmp_path / "sessions").import_state(
            "profile-phase4c",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/9100001/"
        )
        JobRepository(database.connection).create("job-phase4c-replay")
        LiveRunRepository(database.connection).create(
            "job-phase4c-replay",
            "profile-phase4c",
            selected,
            datetime(2026, 7, 1, tzinfo=UTC),
            "app_rendered_html/1.0",
        )
        RawCaptureMetadataRepository(database.connection).add(
            capture_id=capture_id,
            sha256=stored.sha256,
            source_url="https://app.invalid/groups/9100001/",
            collected_at=observed_at,
            storage_path=stored.path.name,
            byte_count=stored.byte_count,
        )
        with database.connection:
            database.connection.execute(
                """
                INSERT INTO tasks(
                    task_id, job_id, idempotency_key, surface, state, created_at, updated_at
                ) VALUES (?, ?, ?, 'group', 'succeeded', ?, ?)
                """,
                (
                    "job-phase4c-replay",
                    "job-phase4c-replay",
                    "group:job-phase4c-replay",
                    observed_at.isoformat(),
                    observed_at.isoformat(),
                ),
            )
            database.connection.execute(
                """
                INSERT INTO pagination_checkpoints(
                    checkpoint_id, task_id, raw_capture_id, cursor,
                    interaction_number, durable_at
                ) VALUES (?, ?, ?, NULL, 1, ?)
                """,
                (
                    "checkpoint-phase4c-replay",
                    "job-phase4c-replay",
                    capture_id,
                    observed_at.isoformat(),
                ),
            )

    replayed = StoredHtmlReplayWorkflow(output, raw_root).replay(
        "job-phase4c-replay",
        offline=True,
    )

    assert replayed.identifiers == (
        "comment:9300001",
        "group:9100001",
        "post:9200001",
    )
    exported = json.loads(
        (output / "exports" / "job-phase4c-replay.json").read_text(encoding="utf-8")
    )
    assert {record["payload"]["session_class"] for record in exported["records"]} == {"imported"}
    assert {record["payload"]["adapter_version"] for record in exported["records"]} == {"1.0"}


@pytest.mark.parametrize("tampered_capture", ["discovery", "confirmation"])
def test_replay_stops_on_tampered_membership_transition_raw(
    tmp_path: Path, tampered_capture: str
) -> None:
    """A joined transition verifies both captured membership pages before exports."""
    output = tmp_path / "operator"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    observed_at = datetime(2026, 7, 30, tzinfo=UTC)
    raw_store = GzipRawCaptureStore(raw_root)
    discovery_html = (
        b"<main><article role='article'><a href='/groups/9100001/'>Garden Bristol</a>"
        b"<button aria-label='Join Group'>Join Group</button></article></main>"
    )
    stored = {
        "discovery": raw_store.write("discovery", discovery_html, suffix=".discovery.html"),
        "confirmation": raw_store.write(
            "confirmation", b"<html>joined</html>", suffix=".confirmation.html"
        ),
        "page": raw_store.write("page", FIXTURE.read_bytes(), suffix=".html"),
    }
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "profile", {"cookies": [], "origins": []}
        )
        raw_captures = RawCaptureMetadataRepository(database.connection)
        for capture in stored.values():
            raw_captures.add(
                capture_id=capture.capture_id,
                sha256=capture.sha256,
                source_url="https://app.invalid/groups/9100001/",
                collected_at=observed_at,
                storage_path=capture.path.name,
                byte_count=capture.byte_count,
            )
        targets = TargetPreparationService(database.connection)
        campaign = targets.add_live_discovery(
            discovery_html,
            keyword="garden",
            location="Bristol",
            source_url="https://app.invalid/groups/search/groups/",
            raw_capture_id=stored["discovery"].capture_id,
        )
        candidate = campaign.membership_preparation_candidates[0]
        targets.plan_join(campaign.campaign_id, candidate.candidate_id, telemetry={})
        targets.complete_join(
            campaign.campaign_id,
            candidate.candidate_id,
            state="joined",
            confirmation_capture_id=stored["confirmation"].capture_id,
            telemetry={},
        )
        selected = targets.select(campaign.campaign_id, candidate.candidate_id)
        JobRepository(database.connection).create("transition-replay")
        LiveRunRepository(database.connection).create(
            "transition-replay",
            "profile",
            selected,
            datetime(2026, 7, 1, tzinfo=UTC),
            "app_rendered_html/1.0",
        )
        database.connection.execute(
            """
            INSERT INTO tasks(
                task_id, job_id, idempotency_key, surface, state, created_at, updated_at
            )
            VALUES ('transition-replay', 'transition-replay', 'group:transition-replay',
                    'group', 'succeeded', ?, ?)
            """,
            (observed_at.isoformat(), observed_at.isoformat()),
        )
        database.connection.execute(
            """
            INSERT INTO pagination_checkpoints(
                checkpoint_id, task_id, raw_capture_id, cursor, interaction_number, durable_at
            ) VALUES ('checkpoint', 'transition-replay', 'page', NULL, 1, ?)
            """,
            (observed_at.isoformat(),),
        )
        database.connection.commit()

    capture = stored[tampered_capture]
    capture.path.write_bytes(gzip.compress(b"tampered", mtime=0))

    with pytest.raises(RawCaptureIntegrityError, match="sha256"):
        StoredHtmlReplayWorkflow(output, raw_root).replay("transition-replay", offline=True)
    assert not (output / "exports" / "transition-replay.json").exists()
