"""Durable context for a resumable selected-Group live capture."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from app.targets.preparation import SelectedTarget


class LiveRunNotFound(RuntimeError):
    """Raised when a requested live capture context does not exist."""


@dataclass(frozen=True)
class LiveRun:
    """Stable capture inputs retained across interruption and resume."""

    job_id: str
    profile_id: str
    campaign_id: str
    group_id: str
    canonical_url: str
    lower_bound: datetime
    adapter_version: str


class LiveRunRepository:
    """Persist immutable live run inputs before page collection begins."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create(
        self,
        job_id: str,
        profile_id: str,
        selected: SelectedTarget,
        lower_bound: datetime,
        adapter_version: str,
    ) -> LiveRun:
        """Create a live run or verify the existing immutable context."""
        if lower_bound.tzinfo is None or lower_bound.utcoffset() is None:
            raise ValueError("lower_bound must be timezone-aware")
        expected = (
            profile_id,
            selected.campaign_id,
            selected.group_id,
            selected.canonical_url,
            lower_bound.astimezone(UTC).isoformat(),
            adapter_version,
        )
        with self.connection:
            row = self.connection.execute(
                "SELECT * FROM live_runs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                self.connection.execute(
                    """
                    INSERT INTO live_runs(
                        job_id, profile_id, campaign_id, group_id, canonical_url,
                        lower_bound, adapter_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, *expected),
                )
            elif tuple(row[key] for key in row if key != "job_id") != expected:
                raise ValueError(f"live run context conflict: {job_id}")
        return self.get(job_id)

    def get(self, job_id: str) -> LiveRun:
        """Return the immutable context required to resume a job."""
        row = self.connection.execute(
            "SELECT * FROM live_runs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise LiveRunNotFound(f"live run not found: {job_id}")
        return LiveRun(
            job_id=row["job_id"],
            profile_id=row["profile_id"],
            campaign_id=row["campaign_id"],
            group_id=row["group_id"],
            canonical_url=row["canonical_url"],
            lower_bound=datetime.fromisoformat(row["lower_bound"]),
            adapter_version=row["adapter_version"],
        )
