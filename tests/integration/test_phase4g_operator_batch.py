"""Local Phase 4G tests for the bounded operator-batch wrapper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.workflows.operator_batch import (
    OperatorBatchTarget,
    OperatorBatchWorkflow,
    OperatorCaptureResult,
    RecoverableOperatorBatchError,
)


def _targets() -> tuple[OperatorBatchTarget, ...]:
    return tuple(
        OperatorBatchTarget(
            group_id=f"GROUP-{index:02d}",
            canonical_url=f"https://app.invalid/groups/GROUP-{index:02d}",
        )
        for index in range(10)
    )


def _capture(target: OperatorBatchTarget) -> OperatorCaptureResult:
    return OperatorCaptureResult(
        run_id=f"run-{target.group_id}",
        identifiers=(
            f"group:{target.group_id}",
            f"post:{target.group_id}",
            f"comment:{target.group_id}",
        ),
        normalized_sha256=target.group_id.lower().ljust(64, "0"),
        raw_sha256=target.group_id.lower().ljust(64, "1"),
    )


def test_operator_batch_completes_ten_targets_with_redacted_aggregate_receipt(
    tmp_path: Path,
) -> None:
    result = OperatorBatchWorkflow(
        tmp_path / "output",
        between_groups_seconds=0,
    ).run(_targets(), _capture)

    assert len(result.groups) == 10
    assert {item.state for item in result.groups} == {"succeeded"}
    assert result.metrics.worker_limit == 1
    assert result.metrics.completed_groups == 10
    assert result.metrics.failed_groups == 0
    assert result.metrics.completeness == 1.0
    assert result.receipt_path.is_file()
    assert result.report_path.is_file()
    payload = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert all(len(item["target_key"]) == 64 for item in payload["groups"])
    assert all("GROUP-" not in json.dumps(item) for item in payload["groups"])


def test_operator_batch_resume_reruns_only_interrupted_targets(tmp_path: Path) -> None:
    calls: list[str] = []
    interrupted = True

    def capture(target: OperatorBatchTarget) -> OperatorCaptureResult:
        nonlocal interrupted
        calls.append(target.group_id)
        if interrupted and len(calls) == 3:
            interrupted = False
            raise KeyboardInterrupt
        return _capture(target)

    workflow = OperatorBatchWorkflow(tmp_path / "output", between_groups_seconds=0)
    with pytest.raises(KeyboardInterrupt):
        workflow.run(_targets(), capture)

    first_calls = calls.copy()
    resumed = workflow.run(_targets(), capture, resume=True)

    assert first_calls == ["GROUP-00", "GROUP-01", "GROUP-02"]
    assert calls[3:] == [f"GROUP-{index:02d}" for index in range(2, 10)]
    assert {item.state for item in resumed.groups} == {"succeeded"}
    assert all(item.attempts == 1 for item in resumed.groups[:2])
    assert resumed.groups[2].attempts == 2


def test_operator_batch_isolates_recoverable_failure_and_resumes_it(tmp_path: Path) -> None:
    failed = {"GROUP-04"}
    calls: list[str] = []

    def capture(target: OperatorBatchTarget) -> OperatorCaptureResult:
        calls.append(target.group_id)
        if target.group_id in failed:
            failed.remove(target.group_id)
            raise RecoverableOperatorBatchError("temporary browser state")
        return _capture(target)

    workflow = OperatorBatchWorkflow(tmp_path / "output", between_groups_seconds=0)
    first = workflow.run(_targets(), capture)
    assert sum(item.state == "incomplete" for item in first.groups) == 1
    assert first.metrics.completed_groups == 9

    calls.clear()
    resumed = workflow.run(_targets(), capture, resume=True)

    assert calls == ["GROUP-04"]
    assert {item.state for item in resumed.groups} == {"succeeded"}
    assert resumed.groups[4].attempts == 2
