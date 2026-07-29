"""Unit tests for deterministic collection metrics."""

from __future__ import annotations

import pytest

from app.metrics import (
    ProcessResourceTimer,
    ResourceSnapshot,
    calculate_throughput,
)


def test_timer_reports_elapsed_cpu_peak_memory_and_storage_delta() -> None:
    wall_times = iter((100.0, 102.5))
    cpu_times = iter((10.0, 11.25))
    resources = iter(
        (
            ResourceSnapshot(memory_bytes=100, storage_bytes=1_000),
            ResourceSnapshot(memory_bytes=250, storage_bytes=1_400),
        )
    )
    timer = ProcessResourceTimer(
        wall_clock=lambda: next(wall_times),
        cpu_clock=lambda: next(cpu_times),
        resource_snapshot=lambda: next(resources),
    )

    timer.start()
    measurement = timer.stop()

    assert measurement.wall_seconds == 2.5
    assert measurement.cpu_seconds == 1.25
    assert measurement.peak_memory_bytes == 250
    assert measurement.storage_delta_bytes == 400


def test_timer_rejects_invalid_lifecycle_and_regressing_measurements() -> None:
    timer = ProcessResourceTimer(
        wall_clock=lambda: 1.0,
        cpu_clock=lambda: 1.0,
        resource_snapshot=lambda: ResourceSnapshot(memory_bytes=1, storage_bytes=1),
    )

    with pytest.raises(RuntimeError, match="not started"):
        timer.stop()

    timer.start()
    with pytest.raises(RuntimeError, match="already started"):
        timer.start()

    regressing = ProcessResourceTimer(
        wall_clock=iter((2.0, 1.0)).__next__,
        cpu_clock=iter((2.0, 1.0)).__next__,
        resource_snapshot=lambda: ResourceSnapshot(memory_bytes=1, storage_bytes=1),
    )
    regressing.start()
    with pytest.raises(ValueError, match="must not move backwards"):
        regressing.stop()


@pytest.mark.parametrize(
    ("posts", "comments", "completeness", "expected_adjusted"),
    [
        (6, 4, 1.0, 20.0),
        (6, 4, 0.75, 15.0),
        (0, 0, 0.0, 0.0),
    ],
)
def test_calculates_completeness_adjusted_throughput(
    posts: int, comments: int, completeness: float, expected_adjusted: float
) -> None:
    metrics = calculate_throughput(
        validated_posts=posts,
        validated_comments=comments,
        completeness=completeness,
        wall_seconds=30.0,
    )

    assert metrics.validated_records == posts + comments
    assert metrics.records_per_minute == (posts + comments) * 2
    assert metrics.completeness_adjusted_records_per_minute == expected_adjusted


@pytest.mark.parametrize(
    ("posts", "comments", "completeness", "wall_seconds"),
    [(-1, 0, 1.0, 1.0), (0, -1, 1.0, 1.0), (0, 0, -0.1, 1.0), (0, 0, 1.1, 1.0), (0, 0, 1.0, 0.0)],
)
def test_rejects_invalid_throughput_inputs(
    posts: int, comments: int, completeness: float, wall_seconds: float
) -> None:
    with pytest.raises(ValueError):
        calculate_throughput(
            validated_posts=posts,
            validated_comments=comments,
            completeness=completeness,
            wall_seconds=wall_seconds,
        )
