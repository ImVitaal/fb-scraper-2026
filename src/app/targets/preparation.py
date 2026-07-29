"""Durable target preparation through direct URL and CSV fallbacks."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4


class TargetPreparationError(ValueError):
    """Raised when a target input or selection is not valid."""


@dataclass(frozen=True)
class TargetCandidate:
    """One durable candidate Group target without private session material."""

    candidate_id: str
    group_id: str
    canonical_url: str
    name: str | None
    source: str
    rank: int

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TargetCampaign:
    """Candidates produced by one direct URL or CSV fallback operation."""

    campaign_id: str
    candidates: tuple[TargetCandidate, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "candidates": [item.as_dict() for item in self.candidates],
        }


@dataclass(frozen=True)
class SelectedTarget:
    """The one selected Group from a target-preparation campaign."""

    campaign_id: str
    candidate_id: str
    group_id: str
    canonical_url: str
    name: str | None
    source: str

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


class TargetPreparationService:
    """Create candidates and enforce exactly one selected target per campaign."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_url(self, url: str) -> SelectedTarget:
        """Create and select one direct Group URL candidate."""
        self._candidate(url, None, "direct_url", 1)
        campaign = self._create_campaign("direct_url", "direct_url")
        candidate = self._add_candidate(campaign, url, None, "direct_url", 1)
        return self.select(campaign, candidate.candidate_id)

    def add_csv(self, csv_path: Path) -> TargetCampaign:
        """Create deduplicated CSV candidates; selection remains explicit."""
        with csv_path.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None or "group_url" not in reader.fieldnames:
                raise TargetPreparationError("CSV requires a group_url header")
            rows = list(reader)
        seen: set[str] = set()
        prepared: list[TargetCandidate] = []
        for row in rows:
            url = row.get("group_url", "")
            candidate = self._candidate(url, row.get("name") or None, "csv", len(prepared) + 1)
            if candidate.canonical_url in seen:
                continue
            seen.add(candidate.canonical_url)
            prepared.append(candidate)
        if not prepared:
            raise TargetPreparationError("CSV has no valid Group URLs")
        campaign = self._create_campaign("csv", "csv")
        candidates = [
            self._add_candidate(campaign, item.canonical_url, item.name, "csv", item.rank)
            for item in prepared
        ]
        return TargetCampaign(campaign, tuple(candidates))

    def select(self, campaign_id: str, candidate_id: str) -> SelectedTarget:
        """Select exactly one existing candidate from one campaign."""
        row = self.connection.execute(
            """
            SELECT hit.hit_id, hit.group_id, hit.canonical_url, hit.name, hit.source
            FROM candidate_hits AS hit
            JOIN discovery_queries AS query ON query.query_id = hit.query_id
            WHERE query.campaign_id = ? AND hit.hit_id = ?
            """,
            (campaign_id, candidate_id),
        ).fetchone()
        if row is None:
            raise TargetPreparationError("candidate does not belong to campaign")
        now = datetime.now(UTC).isoformat()
        with self.connection:
            try:
                self.connection.execute(
                    """
                    INSERT INTO selected_targets(
                        selection_id, campaign_id, group_id, selected_at, candidate_hit_id
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (str(uuid4()), campaign_id, row["group_id"], now, row["hit_id"]),
                )
            except sqlite3.IntegrityError as error:
                raise TargetPreparationError("campaign already has a selected target") from error
        return SelectedTarget(
            campaign_id,
            row["hit_id"],
            row["group_id"],
            row["canonical_url"],
            row["name"],
            row["source"],
        )

    def _create_campaign(self, keyword: str, location: str) -> str:
        campaign_id, query_id = str(uuid4()), str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                "INSERT INTO discovery_campaigns(campaign_id, created_at) VALUES (?, ?)",
                (campaign_id, now),
            )
            self.connection.execute(
                """
                INSERT INTO discovery_queries(query_id, campaign_id, keyword, location, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (query_id, campaign_id, keyword, location, now),
            )
        return campaign_id

    def _add_candidate(
        self, campaign_id: str, url: str, name: str | None, source: str, rank: int
    ) -> TargetCandidate:
        candidate = self._candidate(url, name, source, rank)
        query_id = self.connection.execute(
            "SELECT query_id FROM discovery_queries WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()[0]
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO candidate_hits(
                    hit_id, query_id, group_id, rank, raw_capture_id, observed_at,
                    source, canonical_url, name
                )
                VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    query_id,
                    candidate.group_id,
                    candidate.rank,
                    datetime.now(UTC).isoformat(),
                    candidate.source,
                    candidate.canonical_url,
                    candidate.name,
                ),
            )
        return candidate

    @staticmethod
    def _candidate(url: str, name: str | None, source: str, rank: int) -> TargetCandidate:
        canonical_url, group_id = TargetPreparationService._normalize_group_url(url)
        candidate_id = str(uuid4())
        return TargetCandidate(candidate_id, group_id, canonical_url, name, source, rank)

    @staticmethod
    def _normalize_group_url(url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        path_parts = [part for part in parts.path.split("/") if part]
        if (
            parts.scheme != "https"
            or not parts.netloc
            or len(path_parts) != 2
            or path_parts[0] != "groups"
        ):
            raise TargetPreparationError("Group URL must use https://HOST/groups/GROUP_ID")
        group_id = path_parts[-1]
        if not group_id.replace("-", "").replace("_", "").isalnum():
            raise TargetPreparationError("Group URL has an invalid Group identifier")
        canonical = urlunsplit(("https", parts.netloc.lower(), f"/groups/{group_id}", "", ""))
        return canonical, group_id
