"""Phase 4F local-browser parity across resume, replay, exports, and receipt."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from test_phase4_root_local_browser_vertical import _fixture_server
from typer.testing import CliRunner

from app.capture import PlaywrightGroupCaptureAdapter
from app.cli.main import app
from app.configuration import OperatorProtectionConfiguration
from app.session import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets import TargetPreparationService
from app.workflows.live_capture import LiveCaptureWorkflow

LOWER_BOUND = datetime(2026, 7, 1, tzinfo=UTC)
EXPECTED_IDENTIFIERS = (
    "comment:9300001",
    "group:9100001",
    "post:9200001",
)


def _prepare_run(output: Path, session_root: Path, job_id: str) -> None:
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "phase4f-local-parity",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/9100001"
        )
        JobRepository(database.connection).create(job_id)
        LiveRunRepository(database.connection).create(
            job_id,
            "phase4f-local-parity",
            selected,
            LOWER_BOUND,
            "app_rendered_html/1.0",
        )


def _json_object(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _json_payload(value: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(value))


def _csv_identifiers(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as source:
        return {f"{row['entity_type']}:{row['canonical_id']}" for row in csv.DictReader(source)}


def _sqlite_identifiers(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            identifier for (identifier,) in connection.execute("SELECT identifier FROM records")
        }


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _identifier_hash(identifiers: tuple[str, ...]) -> str:
    payload = json.dumps(
        list(identifiers), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(payload).hexdigest()


@pytest.mark.integration
def test_phase4f_local_browser_resume_replay_export_receipt_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert only current local parity fields; this is not APP evidence.

    Asserted parity fields are the canonical identifier tuple, normalized SHA-256,
    five export-file SHA-256 values, export identifier lists, manifest file hashes,
    receipt identifier-set SHA-256, receipt normalized SHA-256, receipt counts, and
    visible top-level Comment reconciliation.
    """
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    job_id = "phase4f-local-parity"
    _prepare_run(output, session_root, job_id)
    zero_protection = OperatorProtectionConfiguration(
        navigation_delay_seconds=(0.0, 0.0),
        scroll_delay_seconds=(0.0, 0.0),
        expansion_delay_seconds=(0.0, 0.0),
        retry_delays_seconds=(0.0, 0.0),
    )

    with _fixture_server() as (_, local_url):
        interrupted_adapter = PlaywrightGroupCaptureAdapter(
            {"cookies": [], "origins": []},
        )
        with (
            pytest.raises(KeyboardInterrupt),
            interrupted_adapter.capture_pages(local_url, lower_bound=LOWER_BOUND) as capture,
        ):
            LiveCaptureWorkflow(output, raw_root).capture_pages(
                job_id,
                capture,
                max_pages=interrupted_adapter.limits.max_pages,
                interrupt_after_pages=1,
            )
        assert interrupted_adapter.closed

        with Database(output / "scanner.sqlite3") as database:
            state = database.connection.execute(
                "SELECT state FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            checkpoint = database.connection.execute(
                """
                SELECT cursor, interaction_number
                FROM pagination_checkpoints
                WHERE task_id = ?
                ORDER BY interaction_number DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        assert state is not None and state["state"] == "interrupted"
        assert checkpoint is not None
        assert checkpoint["cursor"] is None
        assert checkpoint["interaction_number"] == 1

        class LocalBrowserAdapter(PlaywrightGroupCaptureAdapter):
            def capture_pages(
                self,
                target_url: str,
                *,
                lower_bound: datetime | None = None,
            ):
                return super().capture_pages(local_url, lower_bound=lower_bound)

        monkeypatch.setattr("app.cli.main.PlaywrightGroupCaptureAdapter", LocalBrowserAdapter)
        monkeypatch.setattr("app.cli.main.OperatorProtectionConfiguration", lambda: zero_protection)
        resumed_result = CliRunner().invoke(
            app,
            [
                "resume",
                job_id,
                "--headless",
                "--output",
                str(output),
                "--raw-root",
                str(raw_root),
                "--session-root",
                str(session_root),
            ],
        )

    assert resumed_result.exit_code == 0, resumed_result.output
    resumed_payload = _json_payload(resumed_result.stdout)
    resumed_identifiers = tuple(cast(list[str], resumed_payload["identifiers"]))
    resumed_normalized = str(resumed_payload["normalized_sha256"])
    assert resumed_identifiers == EXPECTED_IDENTIFIERS
    assert resumed_payload["state"] == "succeeded"

    replay_result = CliRunner().invoke(
        app,
        [
            "replay",
            job_id,
            "--offline",
            "--output",
            str(output),
            "--raw-root",
            str(raw_root),
        ],
    )
    assert replay_result.exit_code == 0, replay_result.output
    replay_payload = _json_payload(replay_result.stdout)
    assert tuple(cast(list[str], replay_payload["identifiers"])) == resumed_identifiers
    assert replay_payload["normalized_sha256"] == resumed_normalized

    receipt_path = Path(str(resumed_payload["receipt"]))
    receipt_payload = _json_object(receipt_path)
    export_root = output / "exports"
    export_paths = {
        "csv": export_root / f"{job_id}.csv",
        "json": export_root / f"{job_id}.json",
        "manifest": export_root / f"{job_id}.manifest.json",
        "markdown": export_root / f"{job_id}.md",
        "sqlite": export_root / f"{job_id}.sqlite3",
    }
    export_hashes = {name: _file_hash(path) for name, path in export_paths.items()}

    exported_json = _json_object(export_paths["json"])
    manifest = _json_object(export_paths["manifest"])
    assert tuple(exported_json["identifiers"]) == resumed_identifiers
    assert exported_json["normalized_sha256"] == resumed_normalized
    assert _csv_identifiers(export_paths["csv"]) == set(EXPECTED_IDENTIFIERS)
    assert _sqlite_identifiers(export_paths["sqlite"]) == set(EXPECTED_IDENTIFIERS)
    assert tuple(manifest["identifiers"]) == resumed_identifiers
    assert manifest["normalized_sha256"] == resumed_normalized
    assert manifest["files"] == {
        name: export_hashes[name] for name in ("csv", "json", "markdown", "sqlite")
    }
    markdown = export_paths["markdown"].read_text(encoding="utf-8")
    assert f"Normalized SHA-256: `{resumed_normalized}`" in markdown
    assert all(f"`{identifier}`" in markdown for identifier in EXPECTED_IDENTIFIERS)

    receipt_bytes = receipt_path.read_bytes()
    assert resumed_payload["receipt_sha256"] == sha256(receipt_bytes).hexdigest()
    assert receipt_payload["identifier_set_sha256"] == _identifier_hash(EXPECTED_IDENTIFIERS)
    assert receipt_payload["normalized_sha256"] == resumed_normalized
    assert receipt_payload["counts"] == {
        "comments": 1,
        "failures": 0,
        "groups": 1,
        "posts": 1,
    }
    assert receipt_payload["comment_reconciliation"] == {
        "matched": True,
        "visible_top_level_comments_expected": 1,
        "visible_top_level_comments_exported": 1,
    }
    receipt_exports = cast(dict[str, dict[str, Any]], receipt_payload["exports"])
    assert {name: entry["sha256"] for name, entry in receipt_exports.items()} == export_hashes
    assert {name: entry["byte_count"] for name, entry in receipt_exports.items()} == {
        name: len(path.read_bytes()) for name, path in export_paths.items()
    }
    assert receipt_payload["metrics"]["resume"] is not None
    assert receipt_payload["metrics"]["replay"] is not None
