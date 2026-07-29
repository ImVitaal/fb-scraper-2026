"""Deterministic timing, resource, and throughput measurement primitives."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResourceSnapshot:
    """One process memory and workload-storage observation in bytes."""

    memory_bytes: int
    storage_bytes: int

    def __post_init__(self) -> None:
        if self.memory_bytes < 0 or self.storage_bytes < 0:
            raise ValueError("resource values must be non-negative")


@dataclass(frozen=True)
class ProcessResourceMeasurement:
    """Elapsed process and workload resource measurements."""

    wall_seconds: float
    cpu_seconds: float
    peak_memory_bytes: int
    storage_delta_bytes: int

    def __post_init__(self) -> None:
        if self.wall_seconds < 0 or self.cpu_seconds < 0:
            raise ValueError("timings must be non-negative")
        if self.peak_memory_bytes < 0:
            raise ValueError("peak memory must be non-negative")


@dataclass(frozen=True)
class ThroughputMetrics:
    """Validated record throughput, including completeness adjustment."""

    validated_posts: int
    validated_comments: int
    completeness: float
    wall_seconds: float
    records_per_minute: float
    completeness_adjusted_records_per_minute: float

    @property
    def validated_records(self) -> int:
        """Return the total validated post and comment count."""
        return self.validated_posts + self.validated_comments


@dataclass(frozen=True)
class _TimerStart:
    """Private immutable timer baseline."""

    wall_seconds: float
    cpu_seconds: float
    resources: ResourceSnapshot


class ProcessResourceTimer:
    """Measure process CPU, wall duration, memory, and storage deterministically."""

    def __init__(
        self,
        *,
        storage_root: Path | None = None,
        wall_clock: Callable[[], float] = time.perf_counter,
        cpu_clock: Callable[[], float] = time.process_time,
        resource_snapshot: Callable[[], ResourceSnapshot] | None = None,
    ) -> None:
        self._wall_clock = wall_clock
        self._cpu_clock = cpu_clock
        self._resource_snapshot = resource_snapshot or self._default_snapshot(storage_root)
        self._start: _TimerStart | None = None

    def start(self) -> None:
        """Record a baseline before the measured workflow starts."""
        if self._start is not None:
            raise RuntimeError("timer is already started")
        self._start = _TimerStart(
            wall_seconds=self._wall_clock(),
            cpu_seconds=self._cpu_clock(),
            resources=self._resource_snapshot(),
        )

    def stop(self) -> ProcessResourceMeasurement:
        """Return the measurement and reset the timer for another workflow."""
        start = self._start
        if start is None:
            raise RuntimeError("timer is not started")
        end_wall = self._wall_clock()
        end_cpu = self._cpu_clock()
        end_resources = self._resource_snapshot()
        self._start = None

        wall_seconds = end_wall - start.wall_seconds
        cpu_seconds = end_cpu - start.cpu_seconds
        if wall_seconds < 0 or cpu_seconds < 0:
            raise ValueError("timing clocks must not move backwards")
        return ProcessResourceMeasurement(
            wall_seconds=wall_seconds,
            cpu_seconds=cpu_seconds,
            peak_memory_bytes=max(start.resources.memory_bytes, end_resources.memory_bytes),
            storage_delta_bytes=end_resources.storage_bytes - start.resources.storage_bytes,
        )

    @staticmethod
    def _default_snapshot(storage_root: Path | None) -> Callable[[], ResourceSnapshot]:
        def snapshot() -> ResourceSnapshot:
            storage_bytes = directory_storage_bytes(storage_root) if storage_root else 0
            return ResourceSnapshot(
                memory_bytes=process_memory_bytes(), storage_bytes=storage_bytes
            )

        return snapshot


def calculate_throughput(
    *,
    validated_posts: int,
    validated_comments: int,
    completeness: float,
    wall_seconds: float,
) -> ThroughputMetrics:
    """Calculate validated and completeness-adjusted records per minute."""
    if validated_posts < 0 or validated_comments < 0:
        raise ValueError("validated record counts must be non-negative")
    if not 0.0 <= completeness <= 1.0:
        raise ValueError("completeness must be between zero and one")
    if wall_seconds <= 0:
        raise ValueError("wall_seconds must be positive")

    records_per_minute = (validated_posts + validated_comments) * 60 / wall_seconds
    return ThroughputMetrics(
        validated_posts=validated_posts,
        validated_comments=validated_comments,
        completeness=completeness,
        wall_seconds=wall_seconds,
        records_per_minute=records_per_minute,
        completeness_adjusted_records_per_minute=records_per_minute * completeness,
    )


def directory_storage_bytes(root: Path) -> int:
    """Return the byte size of regular files below one workload storage root."""
    if not root.exists():
        return 0
    if not root.is_dir():
        raise ValueError("storage root must be a directory")
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def process_memory_bytes() -> int:
    """Return current-process resident memory where the platform exposes it."""
    if os.name != "nt":
        return 0

    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("page_fault_count", wintypes.DWORD),
            ("peak_working_set_size", ctypes.c_size_t),
            ("working_set_size", ctypes.c_size_t),
            ("quota_peak_paged_pool_usage", ctypes.c_size_t),
            ("quota_paged_pool_usage", ctypes.c_size_t),
            ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
            ("quota_non_paged_pool_usage", ctypes.c_size_t),
            ("pagefile_usage", ctypes.c_size_t),
            ("peak_pagefile_usage", ctypes.c_size_t),
            ("private_usage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.windll.kernel32.GetCurrentProcess()
    success = ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
    if not success:
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.working_set_size)
