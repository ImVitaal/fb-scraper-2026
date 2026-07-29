"""Retention cleanup for raw capture files and normalized SQLite records."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4


class RetentionError(ValueError):
    """Raised when retention input or storage metadata is invalid."""


@dataclass(frozen=True)
class CleanupReceipt:
    """One durable cleanup result."""

    category: str
    cutoff_at: datetime
    deleted_count: int
    dry_run: bool

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe receipt."""
        return {
            "category": self.category,
            "cutoff_at": self.cutoff_at.isoformat(),
            "deleted_count": self.deleted_count,
            "dry_run": self.dry_run,
        }


class RetentionService:
    """Apply bounded, receipt-backed raw and normalized retention."""

    def __init__(self, connection: sqlite3.Connection, raw_root: Path) -> None:
        self.connection = connection
        self.raw_root = raw_root.resolve()

    def clean(
        self,
        *,
        raw_older_than: str,
        normalized_older_than: str,
        dry_run: bool,
        now: datetime | None = None,
    ) -> tuple[CleanupReceipt, CleanupReceipt]:
        """Clean both retention classes and record one receipt per class."""
        current = (now or datetime.now(UTC)).astimezone(UTC)
        raw_cutoff = current - self._duration(raw_older_than)
        normalized_cutoff = current - self._duration(normalized_older_than)
        raw = self._clean_raw(raw_cutoff, dry_run)
        normalized = self._clean_normalized(normalized_cutoff, dry_run)
        return raw, normalized

    @staticmethod
    def _duration(value: str) -> timedelta:
        match = re.fullmatch(r"([1-9][0-9]*)d", value)
        if match is None:
            raise RetentionError(
                "retention duration must use a positive whole-day value such as 30d"
            )
        return timedelta(days=int(match.group(1)))

    def _clean_raw(self, cutoff: datetime, dry_run: bool) -> CleanupReceipt:
        rows = self.connection.execute(
            """
            SELECT storage_path FROM raw_captures
            WHERE collected_at < ? AND storage_path IS NOT NULL
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        paths = [self._raw_path(str(row["storage_path"])) for row in rows]
        if not dry_run:
            for path in paths:
                if path.is_file():
                    path.unlink()
        return self._record("raw", cutoff, len(paths), dry_run)

    def _clean_normalized(self, cutoff: datetime, dry_run: bool) -> CleanupReceipt:
        cutoff_value = cutoff.isoformat()
        rows = self.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM comments WHERE observed_at < ?) +
                (SELECT COUNT(*) FROM posts WHERE observed_at < ?) +
                (SELECT COUNT(*) FROM groups WHERE observed_at < ?) AS count
            """,
            (cutoff_value, cutoff_value, cutoff_value),
        ).fetchone()
        count = int(rows["count"])
        if not dry_run:
            with self.connection:
                self.connection.execute(
                    """
                    DELETE FROM counter_observations
                    WHERE entity_type = 'comment' AND observed_at < ?
                    """,
                    (cutoff_value,),
                )
                self.connection.execute(
                    "DELETE FROM comments WHERE observed_at < ?", (cutoff_value,)
                )
                self.connection.execute(
                    """
                    DELETE FROM counter_observations
                    WHERE entity_type = 'post' AND observed_at < ?
                    """,
                    (cutoff_value,),
                )
                self.connection.execute("DELETE FROM posts WHERE observed_at < ?", (cutoff_value,))
                self.connection.execute(
                    """
                    DELETE FROM counter_observations
                    WHERE entity_type = 'group' AND observed_at < ?
                    """,
                    (cutoff_value,),
                )
                self.connection.execute("DELETE FROM groups WHERE observed_at < ?", (cutoff_value,))
        return self._record("normalized", cutoff, count, dry_run)

    def _record(
        self, category: str, cutoff: datetime, deleted_count: int, dry_run: bool
    ) -> CleanupReceipt:
        receipt = CleanupReceipt(category, cutoff, deleted_count, dry_run)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO cleanup_receipts(
                    receipt_id, category, cutoff_at, dry_run, deleted_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    category,
                    cutoff.isoformat(),
                    int(dry_run),
                    deleted_count,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return receipt

    def _raw_path(self, storage_path: str) -> Path:
        candidate = (self.raw_root / storage_path).resolve()
        if candidate.parent != self.raw_root:
            raise RetentionError("raw capture storage path escapes the raw root")
        return candidate
