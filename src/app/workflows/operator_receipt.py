"""Stable, non-secret receipt for one controlled operator run."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.capture import BrowserCaptureLimits
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.workflows.fixture_run import WorkflowResult


@dataclass(frozen=True)
class OperatorRunReceipt:
    """Path and SHA-256 for one written operator receipt."""

    path: Path
    sha256: str


class OperatorRunReceiptWriter:
    """Build one receipt from durable database state and completed exports."""

    def __init__(self, output: Path) -> None:
        self.output = output.resolve()
        self.exports = self.output / "exports"

    def write(
        self,
        run_id: str,
        delivery: WorkflowResult,
        limits: BrowserCaptureLimits,
        *,
        protection: Mapping[str, object] | None = None,
    ) -> OperatorRunReceipt:
        """Write hashes, counts, health, limits, and metrics without session material."""
        with Database(self.output / "scanner.sqlite3") as database:
            database.migrate()
            live = LiveRunRepository(database.connection).get(run_id)
            state = JobRepository(database.connection).get_state(run_id)
            profile = database.connection.execute(
                """
                SELECT session_class, health
                FROM session_profiles
                WHERE profile_id = ?
                """,
                (live.profile_id,),
            ).fetchone()
            target = database.connection.execute(
                """
                SELECT hit.source
                FROM selected_targets AS selected
                JOIN candidate_hits AS hit ON hit.hit_id = selected.candidate_hit_id
                WHERE selected.campaign_id = ?
                """,
                (live.campaign_id,),
            ).fetchone()
            raw_rows = database.connection.execute(
                """
                SELECT capture.sha256, capture.byte_count
                FROM pagination_checkpoints AS checkpoint
                JOIN raw_captures AS capture
                  ON capture.capture_id = checkpoint.raw_capture_id
                WHERE checkpoint.task_id = ?
                ORDER BY checkpoint.interaction_number
                """,
                (run_id,),
            ).fetchall()
            counts = database.connection.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM groups WHERE group_id = ?) AS groups,
                  (SELECT COUNT(*) FROM posts WHERE group_id = ?) AS posts,
                  (SELECT COUNT(*) FROM comments WHERE group_id = ?) AS comments
                """,
                (live.group_id, live.group_id, live.group_id),
            ).fetchone()
            post_rows = database.connection.execute(
                "SELECT payload_json FROM posts WHERE group_id = ?",
                (live.group_id,),
            ).fetchall()
            failures = database.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM failures
                WHERE attempt_id IN (SELECT attempt_id FROM attempts WHERE task_id = ?)
                """,
                (run_id,),
            ).fetchone()
        if profile is None or target is None or not raw_rows:
            raise ValueError(f"operator receipt inputs are incomplete: {run_id}")

        raw_captures = [
            {"byte_count": int(row["byte_count"]), "sha256": str(row["sha256"])} for row in raw_rows
        ]
        identifier_set = sorted(delivery.identifiers)
        comments_expected = sum(
            int(json.loads(str(row["payload_json"]))["comments_count"]) for row in post_rows
        )
        comments_exported = int(counts["comments"])
        input_payload = {
            "adapter_version": live.adapter_version,
            "canonical_url_sha256": self._text_sha256(live.canonical_url),
            "lower_bound": live.lower_bound.isoformat(),
            "profile_sha256": self._text_sha256(live.profile_id),
            "target_source": str(target["source"]),
        }
        export_files = {
            name: self._file_entry(self.exports / f"{run_id}.{suffix}")
            for name, suffix in {
                "csv": "csv",
                "json": "json",
                "manifest": "manifest.json",
                "markdown": "md",
                "sqlite": "sqlite3",
            }.items()
        }
        metrics = {
            operation: self._optional_file_entry(
                self.exports / f"{run_id}.{operation}.metrics.json"
            )
            for operation in ("run", "resume", "replay")
        }
        payload = {
            "adapter_version": live.adapter_version,
            "comment_reconciliation": {
                "matched": comments_expected == comments_exported,
                "visible_top_level_comments_expected": comments_expected,
                "visible_top_level_comments_exported": comments_exported,
            },
            "counts": {
                "comments": comments_exported,
                "failures": int(failures["count"]),
                "groups": int(counts["groups"]),
                "posts": int(counts["posts"]),
            },
            "exports": export_files,
            "identifier_set_sha256": self._json_sha256(identifier_set),
            "input": input_payload,
            "input_sha256": self._json_sha256(input_payload),
            "limits": asdict(limits),
            "metrics": metrics,
            "normalized_sha256": delivery.normalized_sha256,
            "protection": dict(protection or {}),
            "raw_captures": raw_captures,
            "raw_set_sha256": self._json_sha256(raw_captures),
            "run_id": run_id,
            "run_type": "operator_html",
            "schema_version": "1.1",
            "session_class": str(profile["session_class"]),
            "session_health": str(profile["health"]),
            "state": state.value,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        path = self.exports / f"{run_id}.operator-receipt.json"
        self._atomic_write(path, encoded)
        return OperatorRunReceipt(path, sha256(encoded).hexdigest())

    def write_stop(
        self,
        run_id: str,
        limits: BrowserCaptureLimits,
        *,
        protection: Mapping[str, object],
        stop_reason: str,
    ) -> OperatorRunReceipt:
        """Write one stable redacted receipt for an immediate browser stop."""
        with Database(self.output / "scanner.sqlite3") as database:
            database.migrate()
            live = LiveRunRepository(database.connection).get(run_id)
            state = JobRepository(database.connection).get_state(run_id)
            profile = database.connection.execute(
                """
                SELECT session_class, health
                FROM session_profiles
                WHERE profile_id = ?
                """,
                (live.profile_id,),
            ).fetchone()
            target = database.connection.execute(
                """
                SELECT hit.source
                FROM selected_targets AS selected
                JOIN candidate_hits AS hit ON hit.hit_id = selected.candidate_hit_id
                WHERE selected.campaign_id = ?
                """,
                (live.campaign_id,),
            ).fetchone()
            raw_rows = database.connection.execute(
                """
                SELECT capture.sha256, capture.byte_count
                FROM pagination_checkpoints AS checkpoint
                JOIN raw_captures AS capture
                  ON capture.capture_id = checkpoint.raw_capture_id
                WHERE checkpoint.task_id = ?
                ORDER BY checkpoint.interaction_number
                """,
                (run_id,),
            ).fetchall()
            counts = database.connection.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM groups WHERE group_id = ?) AS groups,
                  (SELECT COUNT(*) FROM posts WHERE group_id = ?) AS posts,
                  (SELECT COUNT(*) FROM comments WHERE group_id = ?) AS comments
                """,
                (live.group_id, live.group_id, live.group_id),
            ).fetchone()
            identifier_rows = database.connection.execute(
                """
                SELECT 'comment:' || comment_id AS identifier
                FROM comments
                WHERE group_id = ?
                UNION ALL
                SELECT 'group:' || group_id AS identifier
                FROM groups
                WHERE group_id = ?
                UNION ALL
                SELECT 'post:' || post_id AS identifier
                FROM posts
                WHERE group_id = ?
                ORDER BY identifier
                """,
                (live.group_id, live.group_id, live.group_id),
            ).fetchall()
            failures = database.connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM failures
                WHERE attempt_id IN (SELECT attempt_id FROM attempts WHERE task_id = ?)
                """,
                (run_id,),
            ).fetchone()
        if profile is None or target is None:
            raise ValueError(f"operator stop receipt inputs are incomplete: {run_id}")
        raw_captures = [
            {"byte_count": int(row["byte_count"]), "sha256": str(row["sha256"])} for row in raw_rows
        ]
        identifier_set = [str(row["identifier"]) for row in identifier_rows]
        input_payload = {
            "adapter_version": live.adapter_version,
            "canonical_url_sha256": self._text_sha256(live.canonical_url),
            "lower_bound": live.lower_bound.isoformat(),
            "profile_sha256": self._text_sha256(live.profile_id),
            "target_source": str(target["source"]),
        }
        protected = dict(protection)
        protected["stop_reason"] = stop_reason
        payload = {
            "adapter_version": live.adapter_version,
            "counts": {
                "comments": int(counts["comments"]),
                "failures": int(failures["count"]),
                "groups": int(counts["groups"]),
                "posts": int(counts["posts"]),
            },
            "exports": {},
            "identifier_set_sha256": self._json_sha256(identifier_set),
            "input": input_payload,
            "input_sha256": self._json_sha256(input_payload),
            "limits": asdict(limits),
            "metrics": {"replay": None, "resume": None, "run": None},
            "normalized_sha256": None,
            "protection": protected,
            "raw_captures": raw_captures,
            "raw_set_sha256": self._json_sha256(raw_captures),
            "run_id": run_id,
            "run_type": "operator_html",
            "schema_version": "1.0",
            "session_class": str(profile["session_class"]),
            "session_health": str(profile["health"]),
            "state": state.value,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        path = self.exports / f"{run_id}.operator-receipt.json"
        self._atomic_write(path, encoded)
        return OperatorRunReceipt(path, sha256(encoded).hexdigest())

    def write_discovery_stop(
        self,
        receipt_id: str,
        *,
        profile: str,
        protection: Mapping[str, object],
        stop_reason: str,
    ) -> OperatorRunReceipt:
        """Write redacted evidence when protected discovery stops before selection."""
        protected = dict(protection)
        protected["stop_reason"] = stop_reason
        payload = {
            "counts": {"comments": 0, "failures": 1, "groups": 0, "posts": 0},
            "exports": {},
            "input": {"profile_sha256": self._text_sha256(profile)},
            "protection": protected,
            "receipt_id": receipt_id,
            "run_type": "operator_discovery",
            "schema_version": "1.0",
            "state": "failed",
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        path = self.exports / f"{receipt_id}.operator-receipt.json"
        self._atomic_write(path, encoded)
        return OperatorRunReceipt(path, sha256(encoded).hexdigest())

    @staticmethod
    def _text_sha256(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_sha256(value: object) -> str:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @staticmethod
    def _file_entry(path: Path) -> dict[str, object]:
        payload = path.read_bytes()
        return {"byte_count": len(payload), "sha256": sha256(payload).hexdigest()}

    @classmethod
    def _optional_file_entry(cls, path: Path) -> dict[str, object] | None:
        return cls._file_entry(path) if path.is_file() else None

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


__all__ = ["OperatorRunReceipt", "OperatorRunReceiptWriter"]
