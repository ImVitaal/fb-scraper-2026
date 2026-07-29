"""Complete fixture-backed raw-to-replay workflow for Milestone 1A."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.capture import GzipRawCaptureStore, RawCaptureIntegrityError
from app.contracts.models import CollectionHealth, CommentRecord, GroupRecord, JobState, PostRecord
from app.parsing import FixtureCaptureParser
from app.storage.database import Database
from app.storage.repositories import (
    CanonicalRepository,
    JobRepository,
    RawCaptureMetadataRepository,
    RecordNotFound,
)


@dataclass(frozen=True)
class WorkflowResult:
    """Operator-visible result from a fixture run or replay."""

    run_id: str
    identifiers: tuple[str, ...]
    normalized_sha256: str
    output: Path

    def as_dict(self) -> dict[str, object]:
        """Return a stable JSON-safe command result."""
        return {
            "identifiers": list(self.identifiers),
            "normalized_sha256": self.normalized_sha256,
            "output": str(self.output),
            "run_id": self.run_id,
        }


class FixtureWorkflow:
    """Persist raw bytes before parsing, then persist and export canonical records."""

    def __init__(self, output: Path, raw_root: Path) -> None:
        self.output = output.resolve()
        self.database_path = self.output / "scanner.sqlite3"
        self.raw_root = raw_root.resolve()
        repository_root = Path(__file__).resolve().parents[3]
        if (repository_root / ".git").is_dir() and self.raw_root.is_relative_to(repository_root):
            raise ValueError("raw capture root must be outside the repository")
        self.raw_store = GzipRawCaptureStore(self.raw_root)
        self.parser = FixtureCaptureParser()

    def run(self, fixture_path: Path) -> WorkflowResult:
        """Store a synthetic fixture, parse it, and persist/export canonical records."""
        raw_bytes = fixture_path.read_bytes()
        run_id = sha256(raw_bytes).hexdigest()
        stored = self.raw_store.write(run_id, raw_bytes)
        group, posts, comments = self.parser.parse(
            raw_bytes,
            capture_id=stored.capture_id,
            raw_sha256=stored.sha256,
        )
        self._persist(
            stored.capture_id, stored.sha256, stored.path, stored.byte_count, group, posts, comments
        )
        return self._export(stored.capture_id, group, posts, comments)

    def replay(self, run_id: str, *, offline: bool = True) -> WorkflowResult:
        """Read and verify previously stored raw bytes without network access."""
        if not offline:
            raise ValueError("Milestone 1A replay requires --offline")
        with Database(self.database_path) as database:
            database.migrate()
            metadata = RawCaptureMetadataRepository(database.connection).get(run_id)
        storage_key = metadata["storage_path"]
        if storage_key is None:
            raise RawCaptureIntegrityError(f"raw capture storage path missing: {run_id}")
        if storage_key != f"{run_id}.json.gz":
            raise RawCaptureIntegrityError(f"raw capture storage key is invalid: {run_id}")
        raw_path = self.raw_root / str(storage_key)
        raw_bytes = self.raw_store.read(run_id, str(metadata["sha256"]))
        if metadata["byte_count"] is not None and len(raw_bytes) != int(metadata["byte_count"]):
            raise RawCaptureIntegrityError(f"raw capture byte count mismatch: {run_id}")
        group, posts, comments = self.parser.parse(
            raw_bytes,
            capture_id=run_id,
            raw_sha256=str(metadata["sha256"]),
        )
        self._persist(
            run_id,
            str(metadata["sha256"]),
            raw_path,
            len(raw_bytes),
            group,
            posts,
            comments,
        )
        return self._export(run_id, group, posts, comments)

    def _persist(
        self,
        run_id: str,
        digest: str,
        raw_path: Path,
        byte_count: int,
        group: GroupRecord,
        posts: list[PostRecord],
        comments: list[CommentRecord],
    ) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        with Database(self.database_path) as database:
            database.migrate()
            captures = RawCaptureMetadataRepository(database.connection)
            captures.add(
                capture_id=run_id,
                sha256=digest,
                source_url=str(group.source_url),
                collected_at=group.collected_at,
                storage_path=raw_path.name,
                byte_count=byte_count,
            )
            jobs = JobRepository(database.connection)
            try:
                state = jobs.get_state(run_id)
            except RecordNotFound:
                jobs.create(run_id)
                state = JobState.PLANNED
            if state is JobState.PLANNED:
                jobs.transition(run_id, JobState.RUNNING)
            try:
                with database.connection:
                    database.connection.execute(
                        """
                        INSERT OR IGNORE INTO tasks(
                            task_id, job_id, idempotency_key, surface, state, created_at, updated_at
                        ) VALUES (?, ?, ?, 'fixture', 'running', ?, ?)
                        """,
                        (
                            run_id,
                            run_id,
                            f"fixture:{run_id}",
                            group.collected_at.isoformat(),
                            group.collected_at.isoformat(),
                        ),
                    )
                    database.connection.execute(
                        """
                        INSERT OR IGNORE INTO pagination_checkpoints(
                            checkpoint_id, task_id, raw_capture_id, cursor,
                            interaction_number, durable_at
                        ) VALUES (?, ?, ?, NULL, 0, ?)
                        """,
                        (f"checkpoint:{run_id}", run_id, run_id, group.collected_at.isoformat()),
                    )
                records = CanonicalRepository(database.connection)
                records.save_group(group)
                for post in posts:
                    records.save_post(post)
                for comment in comments:
                    records.save_comment(comment)
            except Exception as error:
                self._mark_failed(database, jobs, run_id, group, str(error))
                raise
            with database.connection:
                database.connection.execute(
                    "UPDATE tasks SET state = 'succeeded', updated_at = ? WHERE task_id = ?",
                    (group.collected_at.isoformat(), run_id),
                )
            if jobs.get_state(run_id) is JobState.RUNNING:
                jobs.transition(run_id, JobState.SUCCEEDED)

    @staticmethod
    def _mark_failed(
        database: Database,
        jobs: JobRepository,
        run_id: str,
        group: GroupRecord,
        message: str,
    ) -> None:
        """Leave an explicit durable failure state if persistence cannot finish."""
        with database.connection:
            database.connection.execute(
                "UPDATE tasks SET state = 'failed', updated_at = ? WHERE task_id = ?",
                (group.collected_at.isoformat(), run_id),
            )
            database.connection.execute(
                """
                INSERT OR IGNORE INTO attempts(
                    attempt_id, task_id, attempt_number, health, started_at, finished_at
                ) VALUES (?, ?, 1, ?, ?, ?)
                """,
                (
                    f"attempt:{run_id}:1",
                    run_id,
                    CollectionHealth.PARSER_DRIFT.value,
                    group.collected_at.isoformat(),
                    group.collected_at.isoformat(),
                ),
            )
            database.connection.execute(
                """
                INSERT OR IGNORE INTO failures(
                    failure_id, attempt_id, failure_class, message, recorded_at
                )
                VALUES (?, ?, 'persistence', ?, ?)
                """,
                (
                    f"failure:{run_id}:1",
                    f"attempt:{run_id}:1",
                    message,
                    group.collected_at.isoformat(),
                ),
            )
        if jobs.get_state(run_id) is JobState.RUNNING:
            jobs.transition(run_id, JobState.FAILED)

    def _export(
        self,
        run_id: str,
        group: GroupRecord,
        posts: list[PostRecord],
        comments: list[CommentRecord],
    ) -> WorkflowResult:
        records = self._record_rows(group, posts, comments)
        identifiers = tuple(row["identifier"] for row in records)
        normalized = [
            {key: value for key, value in row.items() if key != "identifier"} for row in records
        ]
        normalized_bytes = json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        normalized_sha256 = sha256(normalized_bytes).hexdigest()
        exports = self.output / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        json_path = exports / f"{run_id}.json"
        csv_path = exports / f"{run_id}.csv"
        json_path.write_text(
            json.dumps(
                {
                    "identifiers": list(identifiers),
                    "normalized_sha256": normalized_sha256,
                    "records": normalized,
                    "run_id": run_id,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with csv_path.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.DictWriter(
                destination, fieldnames=["entity_type", "canonical_id", "payload_json"]
            )
            writer.writeheader()
            for row in records:
                writer.writerow(
                    {
                        "entity_type": row["entity_type"],
                        "canonical_id": row["canonical_id"],
                        "payload_json": json.dumps(
                            row["payload"], sort_keys=True, separators=(",", ":")
                        ),
                    }
                )
        markdown_path = exports / f"{run_id}.md"
        markdown_path.write_text(
            self._markdown_report(run_id, normalized_sha256, identifiers), encoding="utf-8"
        )
        manifest_path = exports / f"{run_id}.manifest.json"
        manifest = {
            "files": {
                "csv": self._file_sha256(csv_path),
                "json": self._file_sha256(json_path),
                "markdown": self._file_sha256(markdown_path),
            },
            "identifiers": list(identifiers),
            "normalized_sha256": normalized_sha256,
            "run_id": run_id,
            "schema_version": "1.0",
            "sqlite": str(self.database_path),
        }
        manifest_bytes = json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        self._record_manifest(run_id, manifest_path, sha256(manifest_bytes).hexdigest())
        return WorkflowResult(run_id, identifiers, normalized_sha256, self.output)

    def _record_manifest(self, run_id: str, manifest_path: Path, manifest_sha256: str) -> None:
        """Persist the operator-visible manifest receipt beside its SQLite output."""
        with Database(self.database_path) as database:
            database.migrate()
            with database.connection:
                database.connection.execute(
                    """
                    INSERT INTO export_manifests(
                        manifest_id, job_id, schema_version, output_path, sha256, created_at
                    ) VALUES (?, ?, '1.0', ?, ?, datetime('now'))
                    ON CONFLICT(manifest_id) DO UPDATE SET
                        output_path = excluded.output_path,
                        sha256 = excluded.sha256,
                        created_at = excluded.created_at
                    """,
                    (f"manifest:{run_id}", run_id, str(manifest_path), manifest_sha256),
                )

    @staticmethod
    def _markdown_report(run_id: str, normalized_sha256: str, identifiers: tuple[str, ...]) -> str:
        """Build a deterministic human-readable export with the canonical identifiers."""
        lines = [
            "# Private Group Scanner export",
            "",
            f"- Run ID: `{run_id}`",
            f"- Normalized SHA-256: `{normalized_sha256}`",
            "",
            "## Canonical identifiers",
            "",
        ]
        lines.extend(f"- `{identifier}`" for identifier in identifiers)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _file_sha256(path: Path) -> str:
        """Return the SHA-256 for one completed export file."""
        return sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _record_rows(
        group: GroupRecord,
        posts: list[PostRecord],
        comments: list[CommentRecord],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "entity_type": "group",
                "canonical_id": group.group_id,
                "identifier": f"group:{group.group_id}",
                "payload": group.model_dump(mode="json"),
            }
        ]
        rows.extend(
            {
                "entity_type": "post",
                "canonical_id": post.post_id,
                "identifier": f"post:{post.post_id}",
                "payload": post.model_dump(mode="json"),
            }
            for post in posts
        )
        rows.extend(
            {
                "entity_type": "comment",
                "canonical_id": comment.comment_id,
                "identifier": f"comment:{comment.comment_id}",
                "payload": comment.model_dump(mode="json"),
            }
            for comment in comments
        )
        return sorted(rows, key=lambda row: str(row["identifier"]))
