"""Deterministic timing, resource, and throughput measurement primitives."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile


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
class MeasurementCounts:
    """Validated output and execution-event counts."""

    groups: int
    posts: int
    comments: int
    retries: int = 0
    failures: int = 0

    def __post_init__(self) -> None:
        if min(self.groups, self.posts, self.comments, self.retries, self.failures) < 0:
            raise ValueError("measurement counts must be non-negative")


@dataclass(frozen=True)
class MeasurementReceipt:
    """One durable measurement receipt for run, resume, or replay."""

    operation: str
    run_id: str
    counts: MeasurementCounts
    duration_seconds: float
    cpu_seconds: float
    peak_memory_bytes: int
    storage_delta_bytes: int
    completeness: float
    records_per_minute: float
    completeness_adjusted_records_per_minute: float
    path: Path

    @property
    def validated_records(self) -> int:
        """Return validated Posts and Comments."""
        return self.counts.posts + self.counts.comments


class MeasurementReceiptWriter:
    """Write stable operation measurements without changing the state schema."""

    _OPERATIONS = frozenset({"run", "resume", "replay"})

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(
        self,
        *,
        operation: str,
        run_id: str,
        counts: MeasurementCounts,
        measurement: ProcessResourceMeasurement,
        completeness: float,
    ) -> MeasurementReceipt:
        """Write one complete JSON measurement receipt atomically."""
        if operation not in self._OPERATIONS:
            raise ValueError("operation must be run, resume, or replay")
        if not run_id:
            raise ValueError("run_id must be non-empty")
        if not 0.0 <= completeness <= 1.0:
            raise ValueError("completeness must be between zero and one")
        if measurement.wall_seconds == 0:
            records_per_minute = 0.0
            adjusted = 0.0
        else:
            throughput = calculate_throughput(
                validated_posts=counts.posts,
                validated_comments=counts.comments,
                completeness=completeness,
                wall_seconds=measurement.wall_seconds,
            )
            records_per_minute = throughput.records_per_minute
            adjusted = throughput.completeness_adjusted_records_per_minute
        receipt_path = self.root / f"{run_id}.{operation}.metrics.json"
        payload = {
            "completeness": completeness,
            "completeness_adjusted_records_per_minute": adjusted,
            "counts": {
                "comments": counts.comments,
                "failures": counts.failures,
                "groups": counts.groups,
                "posts": counts.posts,
                "retries": counts.retries,
            },
            "cpu_seconds": measurement.cpu_seconds,
            "duration_seconds": measurement.wall_seconds,
            "operation": operation,
            "peak_memory_bytes": measurement.peak_memory_bytes,
            "records_per_minute": records_per_minute,
            "run_id": run_id,
            "schema_version": "1.0",
            "storage_delta_bytes": measurement.storage_delta_bytes,
            "validated_records": counts.posts + counts.comments,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_json(receipt_path, payload)
        return MeasurementReceipt(
            operation=operation,
            run_id=run_id,
            counts=counts,
            duration_seconds=measurement.wall_seconds,
            cpu_seconds=measurement.cpu_seconds,
            peak_memory_bytes=measurement.peak_memory_bytes,
            storage_delta_bytes=measurement.storage_delta_bytes,
            completeness=completeness,
            records_per_minute=records_per_minute,
            completeness_adjusted_records_per_minute=adjusted,
            path=receipt_path,
        )

    @staticmethod
    def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as destination:
                temporary = Path(destination.name)
                destination.write(encoded)
                destination.flush()
                os.fsync(destination.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


@dataclass(frozen=True)
class PhaseOneQualityReceipt:
    """Compact Phase 1 correctness and resource evidence."""

    run_id: str
    identifier_precision: float
    required_field_accuracy: float
    pagination_completeness: float
    duplicate_rate: float
    run_resume_match: bool
    run_replay_match: bool
    phase_one_gates_pass: bool
    path: Path


class PhaseOneQualityReceiptWriter:
    """Calculate and write deterministic Phase 1 exit evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(
        self,
        *,
        run_id: str,
        expected_identifiers: Iterable[object],
        run_identifiers: Iterable[object],
        resume_identifiers: Iterable[object],
        replay_identifiers: Iterable[object],
        expected_required_fields: int,
        observed_required_fields: int,
        expected_pages: int,
        observed_pages: int,
        canonical_record_count: int,
        duplicate_count: int,
        retries: int,
        measurement: ProcessResourceMeasurement,
    ) -> PhaseOneQualityReceipt:
        """Write rates, match hashes, retries, and resources in one JSON file."""
        expected = self._identifiers(expected_identifiers, "expected_identifiers")
        run = self._identifiers(run_identifiers, "run_identifiers")
        resume = self._identifiers(resume_identifiers, "resume_identifiers")
        replay = self._identifiers(replay_identifiers, "replay_identifiers")
        values = (
            expected_required_fields,
            observed_required_fields,
            expected_pages,
            observed_pages,
            canonical_record_count,
            duplicate_count,
            retries,
        )
        if min(values) < 0:
            raise ValueError("quality measurement counts must be non-negative")
        if expected_required_fields == 0 or expected_pages == 0 or canonical_record_count == 0:
            raise ValueError("quality measurement denominators must be positive")
        if observed_required_fields > expected_required_fields:
            raise ValueError("observed required fields exceed expected fields")
        if observed_pages > expected_pages:
            raise ValueError("observed pages exceed expected pages")
        if duplicate_count > canonical_record_count:
            raise ValueError("duplicate count exceeds canonical record count")

        expected_set = set(expected)
        run_set = set(run)
        precision = len(run_set & expected_set) / len(run_set) if run_set else 0.0
        required_accuracy = observed_required_fields / expected_required_fields
        pagination_completeness = observed_pages / expected_pages
        duplicate_rate = duplicate_count / canonical_record_count
        run_hash = self._identifier_hash(run)
        resume_hash = self._identifier_hash(resume)
        replay_hash = self._identifier_hash(replay)
        run_resume_match = run_hash == resume_hash
        run_replay_match = run_hash == replay_hash
        gates_pass = (
            precision == 1.0
            and required_accuracy >= 0.99
            and pagination_completeness >= 0.995
            and duplicate_rate <= 0.001
            and run_resume_match
            and run_replay_match
        )
        payload = {
            "duplicate_rate": duplicate_rate,
            "identifier_precision": precision,
            "identifier_set_hashes": {
                "replay": replay_hash,
                "resume": resume_hash,
                "run": run_hash,
            },
            "pagination_completeness": pagination_completeness,
            "phase_one_gates_pass": gates_pass,
            "required_field_accuracy": required_accuracy,
            "resource_metrics": {
                "cpu_seconds": measurement.cpu_seconds,
                "duration_seconds": measurement.wall_seconds,
                "peak_memory_bytes": measurement.peak_memory_bytes,
                "storage_delta_bytes": measurement.storage_delta_bytes,
            },
            "retries": retries,
            "run_id": run_id,
            "run_replay_match": run_replay_match,
            "run_resume_match": run_resume_match,
            "schema_version": "1.0",
        }
        path = self.root / f"{run_id}.phase1-quality.json"
        self.root.mkdir(parents=True, exist_ok=True)
        MeasurementReceiptWriter._atomic_json(path, payload)
        return PhaseOneQualityReceipt(
            run_id=run_id,
            identifier_precision=precision,
            required_field_accuracy=required_accuracy,
            pagination_completeness=pagination_completeness,
            duplicate_rate=duplicate_rate,
            run_resume_match=run_resume_match,
            run_replay_match=run_replay_match,
            phase_one_gates_pass=gates_pass,
            path=path,
        )

    @staticmethod
    def _identifiers(values: Iterable[object], field_name: str) -> tuple[str, ...]:
        identifiers = tuple(str(value) for value in values)
        if any(not value for value in identifiers):
            raise ValueError(f"{field_name} contains an empty identifier")
        return identifiers

    @staticmethod
    def _identifier_hash(identifiers: tuple[str, ...]) -> str:
        encoded = json.dumps(
            sorted(set(identifiers)), separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


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
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    get_process_memory_info.restype = wintypes.BOOL
    process = get_current_process()
    success = get_process_memory_info(process, ctypes.byref(counters), counters.cb)
    if not success:
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.working_set_size)
