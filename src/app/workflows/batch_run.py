"""Sequential Phase 2 fixture collection with isolated terminal Group states."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.metrics import (
    ProcessResourceMeasurement,
    ProcessResourceTimer,
    ResourceSnapshot,
    calculate_throughput,
    directory_storage_bytes,
    process_memory_bytes,
)
from app.workflows.fixture_run import FixtureWorkflow


@dataclass(frozen=True)
class BatchGroupResult:
    """One Group terminal result retained across batch resume."""

    fixture_name: str
    fixture_sha256: str
    state: str
    attempts: int
    run_id: str | None
    identifiers: tuple[str, ...]
    normalized_sha256: str | None
    duration_seconds: float
    error: str | None

    def as_dict(self) -> dict[str, object]:
        """Return a stable receipt payload."""
        return {
            "attempts": self.attempts,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "fixture_name": self.fixture_name,
            "fixture_sha256": self.fixture_sha256,
            "identifiers": list(self.identifiers),
            "normalized_sha256": self.normalized_sha256,
            "run_id": self.run_id,
            "state": self.state,
        }


@dataclass(frozen=True)
class BatchMetrics:
    """Concise Phase 2 aggregate measurements."""

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
        """Return a stable metrics payload."""
        return {
            "completed_groups": self.completed_groups,
            "completeness": self.completeness,
            "completeness_adjusted_records_per_minute": (
                self.completeness_adjusted_records_per_minute
            ),
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
class BatchRunResult:
    """One ten-Group batch receipt and report."""

    groups: tuple[BatchGroupResult, ...]
    metrics: BatchMetrics
    identifier_set_sha256: str
    normalized_set_sha256: str
    receipt_path: Path
    report_path: Path

    def as_dict(self) -> dict[str, object]:
        """Return the operator-visible batch result."""
        return {
            "completed_groups": self.metrics.completed_groups,
            "failed_groups": self.metrics.failed_groups,
            "groups": [group.as_dict() for group in self.groups],
            "identifier_set_sha256": self.identifier_set_sha256,
            "metrics_report": str(self.report_path),
            "normalized_set_sha256": self.normalized_set_sha256,
            "receipt": str(self.receipt_path),
            "worker_limit": self.metrics.worker_limit,
        }


class BatchFixtureWorkflow:
    """Run up to ten synthetic Groups sequentially and resume only incomplete Groups."""

    def __init__(self, output: Path, raw_root: Path) -> None:
        self.output = output.resolve()
        self.raw_root = raw_root.resolve()
        self.receipt_path = self.output / "phase2-batch.json"
        self.report_path = self.output / "phase2-metrics.md"

    def run(self, fixtures: Path, *, resume: bool = False) -> BatchRunResult:
        """Collect one bounded fixture directory with per-Group failure isolation."""
        fixture_paths = self._fixture_paths(fixtures)
        previous = self._previous() if resume else {}
        timer = ProcessResourceTimer(resource_snapshot=self._snapshot)
        timer.start()
        groups: list[BatchGroupResult] = []
        for fixture in fixture_paths:
            digest = sha256(fixture.read_bytes()).hexdigest()
            existing = previous.get(fixture.name)
            if (
                existing is not None
                and existing.state == "succeeded"
                and existing.fixture_sha256 == digest
            ):
                groups.append(existing)
                continue
            attempts = existing.attempts + 1 if existing is not None else 1
            started = time.perf_counter()
            try:
                result = FixtureWorkflow(self.output, self.raw_root).run(fixture)
            except (OSError, ValueError, RuntimeError) as error:
                groups.append(
                    BatchGroupResult(
                        fixture_name=fixture.name,
                        fixture_sha256=digest,
                        state="failed",
                        attempts=attempts,
                        run_id=None,
                        identifiers=(),
                        normalized_sha256=None,
                        duration_seconds=time.perf_counter() - started,
                        error=f"{type(error).__name__}: {error}",
                    )
                )
            else:
                groups.append(
                    BatchGroupResult(
                        fixture_name=fixture.name,
                        fixture_sha256=digest,
                        state="succeeded",
                        attempts=attempts,
                        run_id=result.run_id,
                        identifiers=result.identifiers,
                        normalized_sha256=result.normalized_sha256,
                        duration_seconds=time.perf_counter() - started,
                        error=None,
                    )
                )
            self._write_progress(groups)
        measurement = timer.stop()
        ordered = tuple(sorted(groups, key=lambda group: group.fixture_name))
        identifiers = sorted(
            {
                identifier
                for group in ordered
                if group.state == "succeeded"
                for identifier in group.identifiers
            }
        )
        normalized_hashes = sorted(
            group.normalized_sha256
            for group in ordered
            if group.state == "succeeded" and group.normalized_sha256 is not None
        )
        identifier_set_sha256 = self._set_hash(identifiers)
        normalized_set_sha256 = self._set_hash(normalized_hashes)
        metrics = self._metrics(ordered, measurement)
        result = BatchRunResult(
            groups=ordered,
            metrics=metrics,
            identifier_set_sha256=identifier_set_sha256,
            normalized_set_sha256=normalized_set_sha256,
            receipt_path=self.receipt_path,
            report_path=self.report_path,
        )
        self._write_result(result)
        return result

    @staticmethod
    def _fixture_paths(fixtures: Path) -> tuple[Path, ...]:
        root = fixtures.resolve()
        if not root.is_dir():
            raise ValueError(f"fixture directory does not exist: {fixtures}")
        paths = tuple(sorted(root.glob("*.json")))
        if not 1 <= len(paths) <= 10:
            raise ValueError("batch fixture directory must contain between one and ten JSON files")
        return paths

    def _previous(self) -> dict[str, BatchGroupResult]:
        if not self.receipt_path.is_file():
            return {}
        try:
            payload = json.loads(self.receipt_path.read_text(encoding="utf-8"))
            values = payload["groups"]
            if not isinstance(values, list):
                raise TypeError
            return {
                str(value["fixture_name"]): self._group_from_dict(value)
                for value in values
                if isinstance(value, dict)
            }
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("existing batch receipt is invalid") from error

    @staticmethod
    def _group_from_dict(value: dict[str, Any]) -> BatchGroupResult:
        return BatchGroupResult(
            fixture_name=str(value["fixture_name"]),
            fixture_sha256=str(value["fixture_sha256"]),
            state=str(value["state"]),
            attempts=int(value["attempts"]),
            run_id=str(value["run_id"]) if value.get("run_id") is not None else None,
            identifiers=tuple(str(item) for item in value.get("identifiers", [])),
            normalized_sha256=(
                str(value["normalized_sha256"])
                if value.get("normalized_sha256") is not None
                else None
            ),
            duration_seconds=float(value["duration_seconds"]),
            error=str(value["error"]) if value.get("error") is not None else None,
        )

    def _snapshot(self) -> ResourceSnapshot:
        storage = directory_storage_bytes(self.output) + directory_storage_bytes(self.raw_root)
        return ResourceSnapshot(process_memory_bytes(), storage)

    @staticmethod
    def _metrics(
        groups: tuple[BatchGroupResult, ...],
        measurement: ProcessResourceMeasurement,
    ) -> BatchMetrics:
        completed = sum(group.state == "succeeded" for group in groups)
        failed = len(groups) - completed
        completeness = completed / len(groups)
        posts = sum(
            identifier.startswith("post:") for group in groups for identifier in group.identifiers
        )
        comments = sum(
            identifier.startswith("comment:")
            for group in groups
            for identifier in group.identifiers
        )
        retries = sum(max(group.attempts - 1, 0) for group in groups)
        if measurement.wall_seconds == 0:
            records_per_minute = 0.0
            adjusted = 0.0
        else:
            throughput = calculate_throughput(
                validated_posts=posts,
                validated_comments=comments,
                completeness=completeness,
                wall_seconds=measurement.wall_seconds,
            )
            records_per_minute = throughput.records_per_minute
            adjusted = throughput.completeness_adjusted_records_per_minute
        return BatchMetrics(
            worker_limit=1,
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

    def _write_progress(self, groups: list[BatchGroupResult]) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": [group.as_dict() for group in groups],
            "schema_version": "1.0",
            "state": "running",
        }
        self.receipt_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def _write_result(self, result: BatchRunResult) -> None:
        payload = {
            "groups": [group.as_dict() for group in result.groups],
            "identifier_set_sha256": result.identifier_set_sha256,
            "metrics": result.metrics.as_dict(),
            "normalized_set_sha256": result.normalized_set_sha256,
            "schema_version": "1.0",
            "state": "completed",
        }
        self.receipt_path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        metrics = result.metrics
        lines = [
            "# Phase 2 ten-Group metrics",
            "",
            "- Selected worker limit: `1`",
            "- Selection basis: sequential fixture baseline; no concurrency evidence required.",
            f"- Completed Groups: `{metrics.completed_groups}`",
            f"- Failed Groups: `{metrics.failed_groups}`",
            f"- Completeness: `{metrics.completeness:.6f}`",
            f"- Duration seconds: `{metrics.duration_seconds:.6f}`",
            f"- CPU seconds: `{metrics.cpu_seconds:.6f}`",
            f"- Peak memory bytes: `{metrics.peak_memory_bytes}`",
            f"- Storage delta bytes: `{metrics.storage_delta_bytes}`",
            f"- Retries: `{metrics.retries}`",
            f"- Validated Posts: `{metrics.validated_posts}`",
            f"- Validated Comments: `{metrics.validated_comments}`",
            f"- Records per minute: `{metrics.records_per_minute:.6f}`",
            (
                "- Completeness-adjusted records per minute: "
                f"`{metrics.completeness_adjusted_records_per_minute:.6f}`"
            ),
            f"- Identifier-set SHA-256: `{result.identifier_set_sha256}`",
            f"- Normalized-set SHA-256: `{result.normalized_set_sha256}`",
            "",
            "Each Group has an explicit succeeded or failed terminal state.",
        ]
        self.report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _set_hash(values: list[str]) -> str:
        payload = json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return sha256(payload).hexdigest()
