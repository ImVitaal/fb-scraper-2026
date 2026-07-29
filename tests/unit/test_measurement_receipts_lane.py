"""Behavior tests for durable run, resume, and replay measurements."""

from __future__ import annotations

import json
from pathlib import Path

from app.metrics import (
    MeasurementCounts,
    MeasurementReceiptWriter,
    PhaseOneQualityReceiptWriter,
    ProcessResourceMeasurement,
)


def test_writes_complete_run_resume_and_replay_receipts(tmp_path: Path) -> None:
    writer = MeasurementReceiptWriter(tmp_path)
    measurement = ProcessResourceMeasurement(
        wall_seconds=30.0,
        cpu_seconds=1.25,
        peak_memory_bytes=4096,
        storage_delta_bytes=512,
    )
    counts = MeasurementCounts(
        groups=1,
        posts=6,
        comments=4,
        retries=2,
        failures=1,
    )

    receipts = [
        writer.write(
            operation=operation,
            run_id="run-1",
            counts=counts,
            measurement=measurement,
            completeness=0.75,
        )
        for operation in ("run", "resume", "replay")
    ]

    assert {receipt.operation for receipt in receipts} == {"run", "resume", "replay"}
    for receipt in receipts:
        assert receipt.validated_records == 10
        assert receipt.records_per_minute == 20.0
        assert receipt.completeness_adjusted_records_per_minute == 15.0
        assert receipt.cpu_seconds == 1.25
        assert receipt.peak_memory_bytes == 4096
        assert receipt.storage_delta_bytes == 512
        payload = json.loads(receipt.path.read_text(encoding="utf-8"))
        assert payload["counts"] == {
            "comments": 4,
            "failures": 1,
            "groups": 1,
            "posts": 6,
            "retries": 2,
        }


def test_zero_duration_receipt_has_zero_throughput(tmp_path: Path) -> None:
    receipt = MeasurementReceiptWriter(tmp_path).write(
        operation="replay",
        run_id="empty",
        counts=MeasurementCounts(groups=1, posts=0, comments=0),
        measurement=ProcessResourceMeasurement(0.0, 0.0, 0, 0),
        completeness=1.0,
    )

    assert receipt.records_per_minute == 0.0
    assert receipt.completeness_adjusted_records_per_minute == 0.0


def test_writes_deterministic_phase_one_quality_receipt(tmp_path: Path) -> None:
    identifiers = ("comment:c1", "group:g1", "post:p1")
    receipt = PhaseOneQualityReceiptWriter(tmp_path).write(
        run_id="quality-1",
        expected_identifiers=identifiers,
        run_identifiers=identifiers,
        resume_identifiers=reversed(identifiers),
        replay_identifiers=identifiers,
        expected_required_fields=100,
        observed_required_fields=99,
        expected_pages=200,
        observed_pages=199,
        canonical_record_count=1000,
        duplicate_count=1,
        retries=2,
        measurement=ProcessResourceMeasurement(30.0, 1.0, 4096, 512),
    )

    assert receipt.identifier_precision == 1.0
    assert receipt.required_field_accuracy == 0.99
    assert receipt.pagination_completeness == 0.995
    assert receipt.duplicate_rate == 0.001
    assert receipt.run_resume_match
    assert receipt.run_replay_match
    assert receipt.phase_one_gates_pass
    first = receipt.path.read_bytes()
    second = PhaseOneQualityReceiptWriter(tmp_path).write(
        run_id="quality-1",
        expected_identifiers=identifiers,
        run_identifiers=identifiers,
        resume_identifiers=identifiers,
        replay_identifiers=identifiers,
        expected_required_fields=100,
        observed_required_fields=99,
        expected_pages=200,
        observed_pages=199,
        canonical_record_count=1000,
        duplicate_count=1,
        retries=2,
        measurement=ProcessResourceMeasurement(30.0, 1.0, 4096, 512),
    )
    assert second.path.read_bytes() == first
