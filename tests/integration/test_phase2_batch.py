"""Phase 2 ten-Group sequential reliability acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli.main import app
from app.workflows.batch_run import BatchFixtureWorkflow, BatchRunResult

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ten_groups"


def _identifiers(result: BatchRunResult) -> set[str]:
    return {
        identifier
        for group in result.groups
        for identifier in group.identifiers
        if group.state == "succeeded"
    }


def test_ten_groups_complete_sequentially_with_terminal_states_and_metrics(
    tmp_path: Path,
) -> None:
    result = BatchFixtureWorkflow(tmp_path / "output", tmp_path / "raw").run(FIXTURES)

    assert len(result.groups) == 10
    assert {group.state for group in result.groups} == {"succeeded"}
    assert all(group.attempts == 1 for group in result.groups)
    assert len(_identifiers(result)) == 30
    assert result.metrics.worker_limit == 1
    assert result.metrics.completed_groups == 10
    assert result.metrics.failed_groups == 0
    assert result.metrics.completeness == 1.0
    assert result.metrics.completeness_adjusted_records_per_minute >= 0
    assert result.receipt_path.is_file()
    assert result.report_path.is_file()
    report = result.report_path.read_text(encoding="utf-8")
    assert "Selected worker limit: `1`" in report
    assert "sequential fixture baseline" in report


def test_failure_isolation_and_resume_preserve_completed_groups(tmp_path: Path) -> None:
    workload = tmp_path / "workload"
    workload.mkdir()
    for fixture in sorted(FIXTURES.glob("*.json")):
        (workload / fixture.name).write_bytes(fixture.read_bytes())
    failed_fixture = workload / "group-06.json"
    original = failed_fixture.read_bytes()
    failed_fixture.write_text('{"fixture_version":"unsupported"}', encoding="utf-8")
    output = tmp_path / "output"
    raw = tmp_path / "raw"
    workflow = BatchFixtureWorkflow(output, raw)

    first = workflow.run(workload)

    assert first.metrics.completed_groups == 9
    assert first.metrics.failed_groups == 1
    failed = next(group for group in first.groups if group.fixture_name == "group-06.json")
    assert failed.state == "failed"
    completed_run_ids = {
        group.fixture_name: group.run_id for group in first.groups if group.state == "succeeded"
    }
    failed_fixture.write_bytes(original)

    resumed = workflow.run(workload, resume=True)

    assert {group.state for group in resumed.groups} == {"succeeded"}
    assert resumed.metrics.completed_groups == 10
    assert resumed.metrics.failed_groups == 0
    assert (
        next(group for group in resumed.groups if group.fixture_name == "group-06.json").attempts
        == 2
    )
    for group in resumed.groups:
        if group.fixture_name != "group-06.json":
            assert group.attempts == 1
            assert group.run_id == completed_run_ids[group.fixture_name]


def test_resume_matches_uninterrupted_identifier_and_hash_sets(tmp_path: Path) -> None:
    uninterrupted = BatchFixtureWorkflow(
        tmp_path / "uninterrupted-output", tmp_path / "uninterrupted-raw"
    ).run(FIXTURES)
    resumed_workflow = BatchFixtureWorkflow(tmp_path / "resumed-output", tmp_path / "resumed-raw")
    resumed_workflow.run(FIXTURES)
    resumed = resumed_workflow.run(FIXTURES, resume=True)

    assert _identifiers(resumed) == _identifiers(uninterrupted)
    assert resumed.identifier_set_sha256 == uninterrupted.identifier_set_sha256
    assert resumed.normalized_set_sha256 == uninterrupted.normalized_set_sha256


def test_batch_cli_emits_one_ten_group_receipt(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "batch-run",
            "--fixtures",
            str(FIXTURES),
            "--output",
            str(tmp_path / "output"),
            "--raw-root",
            str(tmp_path / "raw"),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["completed_groups"] == 10
    assert payload["failed_groups"] == 0
    assert payload["worker_limit"] == 1
    assert len(payload["groups"]) == 10
