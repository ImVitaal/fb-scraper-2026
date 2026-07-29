"""End-to-end acceptance tests for the Milestone 1A offline workflow."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from app.cli.main import app

FIXTURE = Path(__file__).parents[1] / "fixtures" / "one_group_capture.json"
EXPECTED_IDENTIFIERS = {
    "comment:comment-fixture-3001",
    "group:group-fixture-1001",
    "post:post-fixture-2001",
}


def _result_payload(stdout: str) -> dict[str, object]:
    return json.loads(stdout)


def _csv_identifiers(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as source:
        return {f"{row['entity_type']}:{row['canonical_id']}" for row in csv.DictReader(source)}


def test_fixture_run_and_offline_replay_produce_identical_identifiers(tmp_path: Path) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "private-raw"
    runner = CliRunner()

    run_result = runner.invoke(
        app,
        ["run", "--fixture", str(FIXTURE), "--output", str(output), "--raw-root", str(raw_root)],
    )

    assert run_result.exit_code == 0, run_result.output
    run_payload = _result_payload(run_result.stdout)
    run_identifiers = run_payload["identifiers"]
    assert isinstance(run_identifiers, list)
    assert set(run_identifiers) == EXPECTED_IDENTIFIERS
    run_id = str(run_payload["run_id"])

    raw_path = raw_root / f"{run_id}.json.gz"
    raw_bytes = FIXTURE.read_bytes()
    assert raw_path.is_file()
    with gzip.open(raw_path, "rb") as capture:
        assert capture.read() == raw_bytes

    database_path = output / "scanner.sqlite3"
    with sqlite3.connect(database_path) as connection:
        capture_row = connection.execute(
            "SELECT sha256, storage_path, byte_count FROM raw_captures WHERE capture_id = ?",
            (run_id,),
        ).fetchone()
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("groups", "posts", "comments")
        }
    assert capture_row == (hashlib.sha256(raw_bytes).hexdigest(), raw_path.name, len(raw_bytes))
    assert counts == {"groups": 1, "posts": 1, "comments": 1}

    assert _csv_identifiers(output / "exports" / f"{run_id}.csv") == EXPECTED_IDENTIFIERS
    export_payload = json.loads((output / "exports" / f"{run_id}.json").read_text(encoding="utf-8"))
    assert set(export_payload["identifiers"]) == EXPECTED_IDENTIFIERS
    markdown = (output / "exports" / f"{run_id}.md").read_text(encoding="utf-8")
    assert all(identifier in markdown for identifier in EXPECTED_IDENTIFIERS)
    manifest_path = output / "exports" / f"{run_id}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest["identifiers"]) == EXPECTED_IDENTIFIERS
    assert (
        manifest["files"]["csv"]
        == hashlib.sha256((output / "exports" / f"{run_id}.csv").read_bytes()).hexdigest()
    )
    with sqlite3.connect(database_path) as connection:
        receipt = connection.execute(
            "SELECT sha256 FROM export_manifests WHERE manifest_id = ?", (f"manifest:{run_id}",)
        ).fetchone()
    assert receipt == (hashlib.sha256(manifest_path.read_bytes()).hexdigest(),)

    replay_result = runner.invoke(
        app,
        ["replay", run_id, "--offline", "--output", str(output), "--raw-root", str(raw_root)],
    )

    assert replay_result.exit_code == 0, replay_result.output
    replay_payload = _result_payload(replay_result.stdout)
    replay_identifiers = replay_payload["identifiers"]
    assert isinstance(replay_identifiers, list)
    assert set(replay_identifiers) == EXPECTED_IDENTIFIERS
    assert replay_identifiers == run_identifiers


def test_offline_replay_rejects_tampered_raw_capture(tmp_path: Path) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "private-raw"
    runner = CliRunner()
    run_result = runner.invoke(
        app,
        ["run", "--fixture", str(FIXTURE), "--output", str(output), "--raw-root", str(raw_root)],
    )
    run_id = str(_result_payload(run_result.stdout)["run_id"])
    raw_path = raw_root / f"{run_id}.json.gz"
    raw_path.write_bytes(b"tampered")

    replay_result = runner.invoke(
        app,
        ["replay", run_id, "--offline", "--output", str(output), "--raw-root", str(raw_root)],
    )

    assert replay_result.exit_code != 0
    assert (
        "sha256" in replay_result.stdout.lower() or "sha256" in str(replay_result.exception).lower()
    )


def test_run_rejects_unsupported_fixture_before_database_persistence(tmp_path: Path) -> None:
    fixture = tmp_path / "unsupported.json"
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["fixture_version"] = "2.0"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "private-raw"

    result = CliRunner().invoke(
        app,
        ["run", "--fixture", str(fixture), "--output", str(output), "--raw-root", str(raw_root)],
    )

    assert result.exit_code != 0
    assert "unsupported" in result.stdout
    assert not (output / "scanner.sqlite3").exists()


def test_run_rejects_a_raw_root_inside_the_repository(tmp_path: Path) -> None:
    output = tmp_path / "operator-data"
    repository_raw_root = Path(__file__).parents[2] / "private-raw-test"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--fixture",
            str(FIXTURE),
            "--output",
            str(output),
            "--raw-root",
            str(repository_raw_root),
        ],
    )

    assert result.exit_code != 0
    assert "outside the repository" in result.stdout


def test_run_accepts_repeatable_toml_configuration(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_bytes(FIXTURE.read_bytes())
    config = tmp_path / "run.toml"
    config.write_text(
        """
        [run]
        fixture = "fixture.json"
        output = "operator-data"
        raw_root = "../private-raw"
        """,
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 0, result.output
    payload = _result_payload(result.stdout)
    identifiers = cast(list[str], payload["identifiers"])
    assert set(identifiers) == EXPECTED_IDENTIFIERS
    assert (tmp_path / "operator-data" / "scanner.sqlite3").is_file()
    assert (tmp_path.parent / "private-raw" / f"{payload['run_id']}.json.gz").is_file()


def test_clean_respects_dry_run_then_removes_expired_raw_and_normalized_records(
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-data"
    raw_root = tmp_path / "private-raw"
    runner = CliRunner()
    run = runner.invoke(
        app,
        ["run", "--fixture", str(FIXTURE), "--output", str(output), "--raw-root", str(raw_root)],
    )
    run_id = str(_result_payload(run.stdout)["run_id"])
    old = "2000-01-01T00:00:00+00:00"
    with sqlite3.connect(output / "scanner.sqlite3") as connection:
        for table, column in (
            ("raw_captures", "collected_at"),
            ("groups", "observed_at"),
            ("posts", "observed_at"),
            ("comments", "observed_at"),
        ):
            connection.execute(f"UPDATE {table} SET {column} = ?", (old,))
        connection.commit()

    dry_run = runner.invoke(
        app,
        [
            "clean",
            "--raw-older-than",
            "30d",
            "--normalized-older-than",
            "90d",
            "--output",
            str(output),
            "--raw-root",
            str(raw_root),
        ],
    )
    assert dry_run.exit_code == 0, dry_run.output
    dry_receipts = cast(list[dict[str, object]], _result_payload(dry_run.stdout)["receipts"])
    assert [receipt["deleted_count"] for receipt in dry_receipts] == [1, 3]
    assert all(receipt["dry_run"] for receipt in dry_receipts)
    assert (raw_root / f"{run_id}.json.gz").is_file()

    applied = runner.invoke(
        app,
        [
            "clean",
            "--raw-older-than",
            "30d",
            "--normalized-older-than",
            "90d",
            "--apply",
            "--output",
            str(output),
            "--raw-root",
            str(raw_root),
        ],
    )
    assert applied.exit_code == 0, applied.output
    assert not (raw_root / f"{run_id}.json.gz").exists()
    with sqlite3.connect(output / "scanner.sqlite3") as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("groups", "posts", "comments")
        }
        receipt_count = connection.execute("SELECT COUNT(*) FROM cleanup_receipts").fetchone()[0]
    assert counts == {"groups": 0, "posts": 0, "comments": 0}
    assert receipt_count == 4
