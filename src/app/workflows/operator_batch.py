"""Bounded sequential batching around the accepted one-Group workflow."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast
from urllib.parse import urlsplit

from app.capture import BrowserStateError
from app.discovery import UnsupportedDiscoveryLayoutError
from app.metrics import (
    ProcessResourceMeasurement,
    ProcessResourceTimer,
    ResourceSnapshot,
    calculate_throughput,
    directory_storage_bytes,
    process_memory_bytes,
)


@dataclass(frozen=True)
class OperatorBatchTarget:
    """One already-selected Group passed to the one-Group capture callback."""

    group_id: str
    canonical_url: str

    @property
    def target_key(self) -> str:
        """Return a redacted stable key for receipts and resume matching."""
        return sha256(f"{self.group_id}\x00{self.canonical_url}".encode()).hexdigest()


@dataclass(frozen=True)
class OperatorCaptureResult:
    """Private in-memory result returned by one accepted Group capture."""

    run_id: str
    identifiers: tuple[str, ...]
    normalized_sha256: str
    raw_sha256: str


class RecoverableOperatorBatchError(RuntimeError):
    """A Group attempt stopped in a state that a later resume may retry."""


class OperatorBatchStopError(RuntimeError):
    """A callback circuit breaker that must halt the remaining Group queue.

    Root adapters should translate session, profile-lock, and other operator
    stop failures into this type when their concrete exception is outside this
    workflow's dependency boundary.
    """

    def __init__(self, stop_reason: str) -> None:
        if not stop_reason or not stop_reason.strip():
            raise ValueError("stop_reason must be non-empty")
        self.stop_reason = stop_reason
        super().__init__(stop_reason)


@dataclass(frozen=True)
class OperatorBatchGroupResult:
    """Redacted terminal state for one ordered Group target."""

    target_key: str
    state: str
    attempts: int
    run_id_sha256: str | None
    identifier_count: int
    identifier_set_sha256: str | None
    normalized_sha256: str | None
    raw_sha256: str | None
    validated_posts: int
    validated_comments: int
    duration_seconds: float
    error_type: str | None
    stop_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "attempts": self.attempts,
            "duration_seconds": self.duration_seconds,
            "error_type": self.error_type,
            "identifier_count": self.identifier_count,
            "identifier_set_sha256": self.identifier_set_sha256,
            "normalized_sha256": self.normalized_sha256,
            "raw_sha256": self.raw_sha256,
            "run_id_sha256": self.run_id_sha256,
            "state": self.state,
            "stop_reason": self.stop_reason,
            "target_key": self.target_key,
            "validated_comments": self.validated_comments,
            "validated_posts": self.validated_posts,
        }


@dataclass(frozen=True)
class OperatorBatchMetrics:
    """Aggregate measurements for one sequential operator-batch attempt."""

    worker_limit: int
    completed_groups: int
    failed_groups: int
    completeness: float
    duration_seconds: float
    cpu_seconds: float
    peak_memory_bytes: int
    storage_delta_bytes: int
    retries: int
    validated_posts: int
    validated_comments: int
    records_per_minute: float
    completeness_adjusted_records_per_minute: float

    def as_dict(self) -> dict[str, object]:
        return {
            "completeness": self.completeness,
            "completeness_adjusted_records_per_minute": (
                self.completeness_adjusted_records_per_minute
            ),
            "completed_groups": self.completed_groups,
            "cpu_seconds": self.cpu_seconds,
            "duration_seconds": self.duration_seconds,
            "failed_groups": self.failed_groups,
            "peak_memory_bytes": self.peak_memory_bytes,
            "records_per_minute": self.records_per_minute,
            "retries": self.retries,
            "storage_delta_bytes": self.storage_delta_bytes,
            "validated_comments": self.validated_comments,
            "validated_posts": self.validated_posts,
            "worker_limit": self.worker_limit,
        }


@dataclass(frozen=True)
class OperatorBatchRunResult:
    """Aggregate result with only redacted per-target fields."""

    groups: tuple[OperatorBatchGroupResult, ...]
    metrics: OperatorBatchMetrics
    identifier_set_sha256: str
    normalized_set_sha256: str
    raw_set_sha256: str
    receipt_path: Path
    report_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "completed_groups": self.metrics.completed_groups,
            "failed_groups": self.metrics.failed_groups,
            "groups": [item.as_dict() for item in self.groups],
            "identifier_set_sha256": self.identifier_set_sha256,
            "metrics_report": str(self.report_path),
            "normalized_set_sha256": self.normalized_set_sha256,
            "raw_set_sha256": self.raw_set_sha256,
            "receipt": str(self.receipt_path),
            "worker_limit": self.metrics.worker_limit,
        }


CaptureOne = Callable[[OperatorBatchTarget], OperatorCaptureResult]


class OperatorBatchWorkflow:
    """Run selected Groups sequentially and resume only incomplete Groups."""

    worker_limit = 1
    max_groups = 10

    def __init__(
        self,
        output: Path,
        raw_root: Path,
        *,
        between_groups_seconds: float = 900.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if between_groups_seconds < 0:
            raise ValueError("between_groups_seconds must be zero or greater")
        self.output = output.resolve()
        self.raw_root = raw_root.resolve()
        repository_root = Path(__file__).resolve().parents[3]
        if self.raw_root.is_relative_to(repository_root):
            raise ValueError("raw capture root must be outside the repository")
        if self.raw_root.is_relative_to(self.output) or self.output.is_relative_to(self.raw_root):
            raise ValueError("raw capture root must be separate from the output root")
        self.between_groups_seconds = between_groups_seconds
        self._sleep = sleep
        self.receipt_path = self.output / "phase4g-batch.json"
        self.report_path = self.output / "phase4g-metrics.md"
        self.identifier_state_path = self.raw_root / "phase4g-identifiers.json"
        self._identifier_values: dict[str, tuple[str, ...]] = {}

    def run(
        self,
        targets: Iterable[OperatorBatchTarget],
        capture_one: CaptureOne,
        *,
        resume: bool = False,
    ) -> OperatorBatchRunResult:
        """Run selected targets in order, preserving durable progress after each."""
        ordered = self._ordered_targets(targets)
        target_keys = tuple(target.target_key for target in ordered)
        previous = self._previous(target_keys) if resume else {}
        if not resume:
            self._identifier_values = {}
            self._write_progress([], target_keys)
        timer = ProcessResourceTimer(resource_snapshot=self._snapshot)
        timer.start()
        groups: list[OperatorBatchGroupResult] = []
        try:
            for target_index, target in enumerate(ordered):
                previous_result = previous.get(target.target_key)
                if previous_result is not None and previous_result.state == "stopped":
                    groups.append(previous_result)
                    break
                if previous_result is not None and previous_result.state != "incomplete":
                    groups.append(previous_result)
                    continue
                if target_index > 0 and groups and self.between_groups_seconds:
                    self._sleep(self.between_groups_seconds)
                attempts = previous_result.attempts + 1 if previous_result else 1
                started = time.perf_counter()
                try:
                    capture = capture_one(target)
                except KeyboardInterrupt:
                    result = self._terminal(
                        target,
                        state="incomplete",
                        attempts=attempts,
                        started=started,
                        error_type="KeyboardInterrupt",
                    )
                    groups.append(result)
                    self._write_progress(groups, target_keys)
                    raise
                except (
                    OperatorBatchStopError,
                    BrowserStateError,
                    UnsupportedDiscoveryLayoutError,
                ) as error:
                    result = self._terminal(
                        target,
                        state="stopped",
                        attempts=attempts,
                        started=started,
                        error_type=type(error).__name__,
                        stop_reason=(
                            error.stop_reason
                            if isinstance(error, OperatorBatchStopError)
                            else (
                                error.failure_class
                                if isinstance(error, BrowserStateError)
                                else "unsupported_discovery_layout"
                            )
                        ),
                    )
                    groups.append(result)
                    self._write_progress(groups, target_keys)
                    break
                except RecoverableOperatorBatchError as error:
                    result = self._terminal(
                        target,
                        state="incomplete",
                        attempts=attempts,
                        started=started,
                        error_type=type(error).__name__,
                    )
                except Exception as error:
                    result = self._terminal(
                        target,
                        state="failed",
                        attempts=attempts,
                        started=started,
                        error_type=type(error).__name__,
                    )
                else:
                    result = self._success(target, capture, attempts, started)
                    self._identifier_values[target.target_key] = tuple(
                        sorted(set(capture.identifiers))
                    )
                groups.append(result)
                self._write_progress(groups, target_keys)
        except KeyboardInterrupt:
            timer.stop()
            raise
        measurement = timer.stop()
        ordered_results = tuple(groups)
        metrics = self._metrics(ordered_results, measurement)
        succeeded = tuple(item for item in ordered_results if item.state == "succeeded")
        result = OperatorBatchRunResult(
            groups=ordered_results,
            metrics=metrics,
            identifier_set_sha256=self._set_hash(
                identifier
                for item in succeeded
                for identifier in self._identifier_values[item.target_key]
            ),
            normalized_set_sha256=self._set_hash(
                sorted(item.normalized_sha256 for item in succeeded if item.normalized_sha256)
            ),
            raw_set_sha256=self._set_hash(
                sorted(item.raw_sha256 for item in succeeded if item.raw_sha256)
            ),
            receipt_path=self.receipt_path,
            report_path=self.report_path,
        )
        self._write_result(result, target_keys)
        return result

    @classmethod
    def _ordered_targets(
        cls, targets: Iterable[OperatorBatchTarget]
    ) -> tuple[OperatorBatchTarget, ...]:
        values = tuple(targets)
        if not 1 <= len(values) <= cls.max_groups:
            raise ValueError("operator batch must contain between one and ten targets")
        for target in values:
            if not isinstance(target.group_id, str) or not target.group_id.strip():
                raise ValueError("operator batch targets require non-empty Group ids")
            if not isinstance(target.canonical_url, str) or not target.canonical_url.strip():
                raise ValueError("operator batch targets require canonical URLs")
            parsed_url = urlsplit(target.canonical_url)
            if parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
                raise ValueError("operator batch targets require absolute HTTPS canonical URLs")
        target_keys = tuple(target.target_key for target in values)
        if len(set(target_keys)) != len(target_keys):
            raise ValueError("operator batch contains duplicate targets")
        group_ids = tuple(target.group_id for target in values)
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("operator batch contains duplicate Group ids")
        canonical_urls = tuple(target.canonical_url for target in values)
        if len(set(canonical_urls)) != len(canonical_urls):
            raise ValueError("operator batch contains duplicate canonical URLs")
        return tuple(sorted(values, key=lambda target: (target.group_id, target.canonical_url)))

    def _previous(
        self, expected_target_keys: tuple[str, ...]
    ) -> dict[str, OperatorBatchGroupResult]:
        if not self.receipt_path.is_file():
            raise ValueError("cannot resume without an existing Phase 4G receipt")
        try:
            payload = json.loads(self.receipt_path.read_text(encoding="utf-8"))
            target_keys = payload["target_keys"]
            if not isinstance(target_keys, list) or not all(
                isinstance(item, str) for item in target_keys
            ):
                raise TypeError
            if len(set(target_keys)) != len(target_keys):
                raise ValueError("existing Phase 4G receipt contains duplicate target keys")
            if tuple(target_keys) != expected_target_keys:
                raise ValueError("existing Phase 4G receipt target set does not match resume")
            if payload["target_set_sha256"] != self._set_hash(target_keys):
                raise ValueError("existing Phase 4G receipt target set hash is invalid")
            self._load_identifier_state(expected_target_keys)
            groups = payload["groups"]
            if not isinstance(groups, list):
                raise TypeError
            results: dict[str, OperatorBatchGroupResult] = {}
            for item in groups:
                if not isinstance(item, dict):
                    raise TypeError
                target_key = item["target_key"]
                if not isinstance(target_key, str) or target_key not in expected_target_keys:
                    raise ValueError("existing Phase 4G receipt contains an unknown target key")
                if target_key in results:
                    raise ValueError("existing Phase 4G receipt contains duplicate target keys")
                result = self._from_dict(item)
                if result.state == "succeeded":
                    if target_key not in self._identifier_values:
                        raise ValueError("existing Phase 4G receipt identifier state is incomplete")
                    identifiers = self._identifier_values[target_key]
                    if result.identifier_count != len(
                        identifiers
                    ) or result.identifier_set_sha256 != (self._set_hash(identifiers)):
                        raise ValueError("existing Phase 4G receipt identifier state is invalid")
                results[target_key] = result
            return results
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("existing Phase 4G receipt is invalid") from error

    @staticmethod
    def _from_dict(value: Mapping[str, object]) -> OperatorBatchGroupResult:
        target_key = value["target_key"]
        state = value["state"]
        if not isinstance(target_key, str) or not isinstance(state, str):
            raise TypeError
        if state not in {"succeeded", "incomplete", "failed", "stopped"}:
            raise ValueError("existing Phase 4G receipt contains an invalid Group state")
        identifier_count = int(cast(int, value.get("identifier_count", 0)))
        return OperatorBatchGroupResult(
            target_key=target_key,
            state=state,
            attempts=int(cast(int, value["attempts"])),
            run_id_sha256=(
                str(value["run_id_sha256"]) if value.get("run_id_sha256") is not None else None
            ),
            identifier_count=identifier_count,
            identifier_set_sha256=(
                str(value["identifier_set_sha256"])
                if value.get("identifier_set_sha256") is not None
                else None
            ),
            normalized_sha256=(
                str(value["normalized_sha256"])
                if value.get("normalized_sha256") is not None
                else None
            ),
            raw_sha256=str(value["raw_sha256"]) if value.get("raw_sha256") is not None else None,
            validated_posts=int(cast(int, value.get("validated_posts", 0))),
            validated_comments=int(cast(int, value.get("validated_comments", 0))),
            duration_seconds=float(cast(float, value["duration_seconds"])),
            error_type=str(value["error_type"]) if value.get("error_type") is not None else None,
            stop_reason=(
                str(value["stop_reason"]) if value.get("stop_reason") is not None else None
            ),
        )

    @staticmethod
    def _success(
        target: OperatorBatchTarget,
        capture: OperatorCaptureResult,
        attempts: int,
        started: float,
    ) -> OperatorBatchGroupResult:
        identifiers = tuple(sorted(set(capture.identifiers)))
        return OperatorBatchGroupResult(
            target_key=target.target_key,
            state="succeeded",
            attempts=attempts,
            run_id_sha256=sha256(capture.run_id.encode()).hexdigest(),
            identifier_count=len(identifiers),
            identifier_set_sha256=OperatorBatchWorkflow._set_hash(identifiers),
            normalized_sha256=capture.normalized_sha256,
            raw_sha256=capture.raw_sha256,
            validated_posts=sum(item.startswith("post:") for item in identifiers),
            validated_comments=sum(item.startswith("comment:") for item in identifiers),
            duration_seconds=time.perf_counter() - started,
            error_type=None,
        )

    @staticmethod
    def _terminal(
        target: OperatorBatchTarget,
        *,
        state: str,
        attempts: int,
        started: float,
        error_type: str,
        stop_reason: str | None = None,
    ) -> OperatorBatchGroupResult:
        return OperatorBatchGroupResult(
            target_key=target.target_key,
            state=state,
            attempts=attempts,
            run_id_sha256=None,
            identifier_count=0,
            identifier_set_sha256=None,
            normalized_sha256=None,
            raw_sha256=None,
            validated_posts=0,
            validated_comments=0,
            duration_seconds=time.perf_counter() - started,
            error_type=error_type,
            stop_reason=stop_reason,
        )

    def _snapshot(self) -> ResourceSnapshot:
        return ResourceSnapshot(
            memory_bytes=process_memory_bytes(),
            storage_bytes=directory_storage_bytes(self.output)
            + directory_storage_bytes(self.raw_root),
        )

    @staticmethod
    def _metrics(
        groups: tuple[OperatorBatchGroupResult, ...],
        measurement: ProcessResourceMeasurement,
    ) -> OperatorBatchMetrics:
        completed = sum(item.state == "succeeded" for item in groups)
        failed = len(groups) - completed
        completeness = completed / len(groups)
        posts = sum(item.validated_posts for item in groups)
        comments = sum(item.validated_comments for item in groups)
        retries = sum(max(item.attempts - 1, 0) for item in groups)
        if measurement.wall_seconds:
            throughput = calculate_throughput(
                validated_posts=posts,
                validated_comments=comments,
                completeness=completeness,
                wall_seconds=measurement.wall_seconds,
            )
            records_per_minute = throughput.records_per_minute
            adjusted = throughput.completeness_adjusted_records_per_minute
        else:
            records_per_minute = 0.0
            adjusted = 0.0
        return OperatorBatchMetrics(
            worker_limit=OperatorBatchWorkflow.worker_limit,
            completed_groups=completed,
            failed_groups=failed,
            completeness=completeness,
            duration_seconds=measurement.wall_seconds,
            cpu_seconds=measurement.cpu_seconds,
            peak_memory_bytes=measurement.peak_memory_bytes,
            storage_delta_bytes=measurement.storage_delta_bytes,
            retries=retries,
            validated_posts=posts,
            validated_comments=comments,
            records_per_minute=records_per_minute,
            completeness_adjusted_records_per_minute=adjusted,
        )

    def _write_progress(
        self,
        groups: list[OperatorBatchGroupResult],
        target_keys: tuple[str, ...],
    ) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": [item.as_dict() for item in groups],
            "schema_version": "1.0",
            "state": "running",
            "target_keys": list(target_keys),
            "target_set_sha256": self._set_hash(target_keys),
            "worker_limit": self.worker_limit,
        }
        self._atomic_json(self.receipt_path, payload)
        # Publish the receipt first. If the identifier sidecar replacement fails,
        # resume rejects the newer receipt rather than mixing generations.
        self._write_identifier_state(target_keys)

    def _write_result(self, result: OperatorBatchRunResult, target_keys: tuple[str, ...]) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": [item.as_dict() for item in result.groups],
            "identifier_set_sha256": result.identifier_set_sha256,
            "metrics": result.metrics.as_dict(),
            "normalized_set_sha256": result.normalized_set_sha256,
            "raw_set_sha256": result.raw_set_sha256,
            "schema_version": "1.0",
            "state": "stopped"
            if any(item.state == "stopped" for item in result.groups)
            else "completed",
            "target_keys": list(target_keys),
            "target_set_sha256": self._set_hash(target_keys),
        }
        self._atomic_json(self.receipt_path, payload)
        metrics = result.metrics
        lines = [
            "# Phase 4G sequential operator batch",
            "",
            f"- Worker limit: `{metrics.worker_limit}`",
            f"- Completed Groups: `{metrics.completed_groups}`",
            f"- Incomplete or failed Groups: `{metrics.failed_groups}`",
            f"- Completeness: `{metrics.completeness:.6f}`",
            f"- Retries: `{metrics.retries}`",
            f"- Records per minute: `{metrics.records_per_minute:.6f}`",
            (
                "- Completeness-adjusted records per minute: "
                f"`{metrics.completeness_adjusted_records_per_minute:.6f}`"
            ),
            f"- Identifier-set SHA-256: `{result.identifier_set_sha256}`",
            f"- Normalized-set SHA-256: `{result.normalized_set_sha256}`",
            f"- Raw-set SHA-256: `{result.raw_set_sha256}`",
        ]
        stop_reasons = sorted(
            {item.stop_reason for item in result.groups if item.stop_reason is not None}
        )
        if stop_reasons:
            lines.append(f"- Stop reasons: `{', '.join(stop_reasons)}`")
        self._atomic_write(self.report_path, ("\n".join(lines) + "\n").encode("utf-8"))

    @staticmethod
    def _set_hash(values: Iterable[str]) -> str:
        payload = json.dumps(sorted(set(values)), separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        return sha256(payload).hexdigest()

    def _write_identifier_state(self, target_keys: tuple[str, ...]) -> None:
        payload = {
            "identifiers": {
                target_key: list(self._identifier_values[target_key])
                for target_key in target_keys
                if target_key in self._identifier_values
            },
            "schema_version": "1.0",
            "target_keys": list(target_keys),
            "target_set_sha256": self._set_hash(target_keys),
        }
        self._atomic_json(self.identifier_state_path, payload)

    def _load_identifier_state(self, expected_target_keys: tuple[str, ...]) -> None:
        if not self.identifier_state_path.is_file():
            raise ValueError("existing Phase 4G identifier state is missing")
        try:
            payload = json.loads(self.identifier_state_path.read_text(encoding="utf-8"))
            target_keys = payload["target_keys"]
            if not isinstance(target_keys, list) or not all(
                isinstance(item, str) for item in target_keys
            ):
                raise TypeError
            if tuple(target_keys) != expected_target_keys:
                raise ValueError("existing Phase 4G identifier state target set does not match")
            if payload["target_set_sha256"] != self._set_hash(target_keys):
                raise ValueError("existing Phase 4G identifier state target set hash is invalid")
            values = payload["identifiers"]
            if not isinstance(values, dict):
                raise TypeError
            state: dict[str, tuple[str, ...]] = {}
            for target_key, identifiers in values.items():
                if target_key not in expected_target_keys:
                    raise ValueError("existing Phase 4G identifier state has an unknown target")
                if not isinstance(identifiers, list) or not all(
                    isinstance(item, str) for item in identifiers
                ):
                    raise TypeError
                if len(set(identifiers)) != len(identifiers):
                    raise ValueError("existing Phase 4G identifier state contains duplicates")
                state[target_key] = tuple(identifiers)
            self._identifier_values = state
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("existing Phase 4G identifier state is invalid") from error

    @staticmethod
    def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        OperatorBatchWorkflow._atomic_write(path, encoded)

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as target:
                temporary = Path(target.name)
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
