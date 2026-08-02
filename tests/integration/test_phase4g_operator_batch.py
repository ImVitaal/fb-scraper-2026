"""Local Phase 4G tests for the bounded operator-batch wrapper."""

from __future__ import annotations

import json
from hashlib import sha256
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


def _canonical_identifier_union_hash(identifiers: tuple[str, ...]) -> str:
    payload = json.dumps(
        sorted(set(identifiers)), separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def test_operator_batch_completes_ten_targets_with_redacted_aggregate_receipt(
    tmp_path: Path,
) -> None:
    result = OperatorBatchWorkflow(
        tmp_path / "output",
        tmp_path / "raw",
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

    workflow = OperatorBatchWorkflow(
        tmp_path / "output",
        tmp_path / "raw",
        between_groups_seconds=0,
    )
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

    workflow = OperatorBatchWorkflow(
        tmp_path / "output",
        tmp_path / "raw",
        between_groups_seconds=0,
    )
    first = workflow.run(_targets(), capture)
    assert sum(item.state == "incomplete" for item in first.groups) == 1
    assert first.metrics.completed_groups == 9

    calls.clear()
    resumed = workflow.run(_targets(), capture, resume=True)

    assert calls == ["GROUP-04"]
    assert {item.state for item in resumed.groups} == {"succeeded"}
    assert resumed.groups[4].attempts == 2


def test_operator_batch_requires_a_separate_external_raw_root(tmp_path: Path) -> None:
    repository_root = Path(__file__).parents[2]
    with pytest.raises(ValueError, match="outside the repository"):
        OperatorBatchWorkflow(repository_root / "output", repository_root / "raw")

    with pytest.raises(ValueError, match="separate from the output"):
        OperatorBatchWorkflow(tmp_path / "output", tmp_path / "output" / "raw")

    with pytest.raises(ValueError, match="separate from the output"):
        OperatorBatchWorkflow(tmp_path / "output", tmp_path)


def test_operator_batch_rejects_duplicate_targets(tmp_path: Path) -> None:
    targets = _targets()[:2]
    duplicate = (targets[0], targets[1], targets[0])
    output = tmp_path / "output"
    raw = tmp_path / "raw"

    with pytest.raises(ValueError, match="duplicate"):
        OperatorBatchWorkflow(
            output,
            raw,
            between_groups_seconds=0,
        ).run(
            duplicate,
            _capture,
        )
    assert not output.exists()
    assert not raw.exists()

    same_url = (
        OperatorBatchTarget("GROUP-A", "https://app.invalid/groups/shared"),
        OperatorBatchTarget("GROUP-B", "https://app.invalid/groups/shared"),
    )
    with pytest.raises(ValueError, match="duplicate"):
        OperatorBatchWorkflow(
            tmp_path / "output-urls",
            tmp_path / "raw-urls",
            between_groups_seconds=0,
        ).run(same_url, _capture)
    assert not (tmp_path / "output-urls").exists()
    assert not (tmp_path / "raw-urls").exists()


def test_operator_batch_resume_rejects_a_changed_target_set(tmp_path: Path) -> None:
    workflow = OperatorBatchWorkflow(
        tmp_path / "output",
        tmp_path / "raw",
        between_groups_seconds=0,
    )
    workflow.run(_targets()[:2], _capture)

    with pytest.raises(ValueError, match="target set"):
        workflow.run(_targets()[:1], _capture, resume=True)


def test_operator_batch_resume_rejects_duplicate_progress_entries(tmp_path: Path) -> None:
    workflow = OperatorBatchWorkflow(
        tmp_path / "output",
        tmp_path / "raw",
        between_groups_seconds=0,
    )
    workflow.run(_targets()[:2], _capture)

    payload = json.loads(workflow.receipt_path.read_text(encoding="utf-8"))
    payload["groups"].append(payload["groups"][0])
    workflow.receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        workflow.run(_targets()[:2], _capture, resume=True)


def test_operator_batch_progress_write_preserves_previous_receipt_on_replace_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = OperatorBatchWorkflow(tmp_path / "output", tmp_path / "raw")
    workflow.output.mkdir(parents=True)
    workflow.receipt_path.write_text('{"state":"old"}', encoding="utf-8")

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        workflow._write_progress([], tuple(target.target_key for target in _targets()[:2]))

    assert workflow.receipt_path.read_text(encoding="utf-8") == '{"state":"old"}'
    assert not tuple(workflow.output.glob("*.tmp"))


def test_operator_batch_hashes_the_canonical_identifier_union(tmp_path: Path) -> None:
    targets = _targets()[:2]

    def capture_with_overlap(target: OperatorBatchTarget) -> OperatorCaptureResult:
        return OperatorCaptureResult(
            run_id=f"run-{target.group_id}",
            identifiers=(
                f"group:{target.group_id}",
                "post:SHARED",
                "comment:SHARED",
                "post:SHARED",
            ),
            normalized_sha256=target.group_id.lower().ljust(64, "0"),
            raw_sha256=target.group_id.lower().ljust(64, "1"),
        )

    workflow = OperatorBatchWorkflow(
        tmp_path / "output",
        tmp_path / "raw",
        between_groups_seconds=0,
    )
    result = workflow.run(targets, capture_with_overlap)

    expected = _canonical_identifier_union_hash(
        (
            "group:GROUP-00",
            "group:GROUP-01",
            "post:SHARED",
            "comment:SHARED",
        )
    )
    assert result.identifier_set_sha256 == expected
    assert result.groups[0].identifier_count == 3
    resumed = workflow.run(targets, capture_with_overlap, resume=True)
    assert resumed.identifier_set_sha256 == expected
