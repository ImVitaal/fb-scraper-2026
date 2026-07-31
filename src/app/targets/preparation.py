"""Durable target preparation through direct URL and CSV fallbacks."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.discovery import AppDiscoveryParser, DiscoveryParser, MembershipState


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
    activity_posts_per_day: int | None = None
    membership: MembershipState = MembershipState.JOINED

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TargetCampaign:
    """Candidates produced by one direct URL or CSV fallback operation."""

    campaign_id: str
    candidates: tuple[TargetCandidate, ...]
    membership_preparation_candidates: tuple[TargetCandidate, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "candidates": [item.as_dict() for item in self.candidates],
            "membership_preparation_candidates": [
                item.as_dict() for item in self.membership_preparation_candidates
            ],
        }

    @property
    def requires_membership_preparation(self) -> bool:
        """Whether discovery surfaced Groups that require membership before collection."""
        return bool(self.membership_preparation_candidates)


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

    def add_discovery(self, raw_html: bytes, *, keyword: str, location: str) -> TargetCampaign:
        """Persist ranked candidates from one supported discovery-page capture."""
        result = DiscoveryParser().parse(raw_html, keyword=keyword, location=location)
        if not result.candidates:
            raise TargetPreparationError("discovery returned no Group candidates")
        campaign = self._create_campaign(result.keyword, result.location)
        candidates = [
            self._add_candidate(
                campaign,
                candidate.canonical_url,
                candidate.name,
                "discovery",
                candidate.rank,
            )
            for candidate in result.candidates
        ]
        return TargetCampaign(campaign, tuple(candidates))

    def add_live_discovery(
        self,
        raw_html: bytes,
        *,
        keyword: str,
        location: str,
        source_url: str,
        raw_capture_id: str,
    ) -> TargetCampaign:
        """Persist ranked candidates from one raw-first APP discovery capture."""
        result = AppDiscoveryParser().parse(
            raw_html,
            keyword=keyword,
            location=location,
            source_url=source_url,
        )
        campaign = self._create_campaign(result.keyword, result.location)
        all_candidates = [
            self._add_candidate(
                campaign,
                candidate.canonical_url,
                candidate.name,
                "discovery",
                candidate.rank,
                raw_capture_id=raw_capture_id,
                activity_posts_per_day=candidate.activity_posts_per_day,
                membership=candidate.membership,
            )
            for candidate in result.candidates
        ]
        candidates = tuple(
            candidate
            for candidate in all_candidates
            if candidate.membership is MembershipState.JOINED
        )
        preparation = tuple(
            candidate
            for candidate in all_candidates
            if candidate.membership is not MembershipState.JOINED
        )
        return TargetCampaign(campaign, candidates, preparation)

    def plan_join(
        self, campaign_id: str, candidate_id: str, *, telemetry: dict[str, object]
    ) -> TargetCandidate:
        """Durably reserve exactly one eligible discovery candidate before its join click."""
        row = self._candidate_row(campaign_id, candidate_id)
        if row["membership_state"] != MembershipState.JOIN_AVAILABLE.value:
            raise TargetPreparationError("candidate is not available for a join action")
        now = datetime.now(UTC).isoformat()
        with self.connection:
            try:
                self.connection.execute(
                    """
                    INSERT INTO membership_transitions(
                        transition_id, campaign_id, candidate_hit_id, group_id, action, state,
                        planned_at, telemetry_json
                    ) VALUES (?, ?, ?, ?, 'join', 'planned', ?, ?)
                    """,
                    (
                        str(uuid4()),
                        campaign_id,
                        candidate_id,
                        row["group_id"],
                        now,
                        json.dumps(telemetry, sort_keys=True, separators=(",", ":")),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise TargetPreparationError(
                    "candidate already has a membership transition"
                ) from error
        return self._target_candidate(row)

    def complete_join(
        self,
        campaign_id: str,
        candidate_id: str,
        *,
        state: str,
        confirmation_capture_id: str | None,
        telemetry: dict[str, object],
    ) -> TargetCandidate:
        """Record the single join outcome and unlock a confirmed candidate for selection."""
        if state not in {"joined", "pending", "rejected", "stopped"}:
            raise TargetPreparationError("membership transition has an invalid state")
        self._candidate_row(campaign_id, candidate_id)
        now = datetime.now(UTC).isoformat()
        with self.connection:
            updated = self.connection.execute(
                """
                UPDATE membership_transitions
                SET state = ?, actioned_at = ?, completed_at = ?, confirmation_capture_id = ?,
                    telemetry_json = ?
                WHERE campaign_id = ? AND candidate_hit_id = ? AND state = 'planned'
                """,
                (
                    state,
                    now,
                    now,
                    confirmation_capture_id,
                    json.dumps(telemetry, sort_keys=True, separators=(",", ":")),
                    campaign_id,
                    candidate_id,
                ),
            ).rowcount
            if updated != 1:
                raise TargetPreparationError("membership transition is not awaiting completion")
            if state == "joined":
                self.connection.execute(
                    "UPDATE candidate_hits SET membership_state = 'joined' WHERE hit_id = ?",
                    (candidate_id,),
                )
        return self._target_candidate(self._candidate_row(campaign_id, candidate_id))

    def attempted_join_group_ids(self) -> set[str]:
        """Return durable one-time join reservations across prior operator runs."""
        rows = self.connection.execute(
            "SELECT DISTINCT group_id FROM membership_transitions"
        ).fetchall()
        return {str(row["group_id"]) for row in rows}

    def select(self, campaign_id: str, candidate_id: str) -> SelectedTarget:
        """Select exactly one existing candidate from one campaign."""
        row = self.connection.execute(
            """
            SELECT hit.hit_id, hit.group_id, hit.canonical_url, hit.name, hit.source,
                   hit.membership_state, hit.rank
            FROM candidate_hits AS hit
            JOIN discovery_queries AS query ON query.query_id = hit.query_id
            WHERE query.campaign_id = ? AND hit.hit_id = ?
            """,
            (campaign_id, candidate_id),
        ).fetchone()
        if row is None:
            raise TargetPreparationError("candidate does not belong to campaign")
        if row["membership_state"] != MembershipState.JOINED.value:
            raise TargetPreparationError("candidate membership is not confirmed")
        existing = self.connection.execute(
            "SELECT candidate_hit_id FROM selected_targets WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        if existing is not None:
            if existing["candidate_hit_id"] == candidate_id:
                return SelectedTarget(
                    campaign_id,
                    row["hit_id"],
                    row["group_id"],
                    row["canonical_url"],
                    row["name"],
                    row["source"],
                )
            raise TargetPreparationError("campaign already has a different selected target")
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

    def get_selected(self, campaign_id: str) -> SelectedTarget:
        """Return the one selected candidate required by a live capture campaign."""
        row = self.connection.execute(
            """
            SELECT selection.campaign_id, hit.hit_id, hit.group_id,
                   hit.canonical_url, hit.name, hit.source
            FROM selected_targets AS selection
            JOIN candidate_hits AS hit ON hit.hit_id = selection.candidate_hit_id
            WHERE selection.campaign_id = ?
            """,
            (campaign_id,),
        ).fetchone()
        if row is None:
            raise TargetPreparationError("campaign has no selected target")
        return SelectedTarget(
            row["campaign_id"],
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
        self,
        campaign_id: str,
        url: str,
        name: str | None,
        source: str,
        rank: int,
        *,
        raw_capture_id: str | None = None,
        activity_posts_per_day: int | None = None,
        membership: MembershipState = MembershipState.JOINED,
    ) -> TargetCandidate:
        candidate = self._candidate(
            url,
            name,
            source,
            rank,
            activity_posts_per_day=activity_posts_per_day,
            membership=membership,
        )
        query_id = self.connection.execute(
            "SELECT query_id FROM discovery_queries WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()[0]
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO candidate_hits(
                    hit_id, query_id, group_id, rank, raw_capture_id, observed_at,
                    source, canonical_url, name, membership_state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    query_id,
                    candidate.group_id,
                    candidate.rank,
                    raw_capture_id,
                    datetime.now(UTC).isoformat(),
                    candidate.source,
                    candidate.canonical_url,
                    candidate.name,
                    candidate.membership.value,
                ),
            )
        return candidate

    def _candidate_row(self, campaign_id: str, candidate_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT hit.hit_id, hit.group_id, hit.canonical_url, hit.name, hit.source,
                   hit.rank, hit.membership_state
            FROM candidate_hits AS hit
            JOIN discovery_queries AS query ON query.query_id = hit.query_id
            WHERE query.campaign_id = ? AND hit.hit_id = ?
            """,
            (campaign_id, candidate_id),
        ).fetchone()
        if row is None:
            raise TargetPreparationError("candidate does not belong to campaign")
        return row

    @staticmethod
    def _target_candidate(row: sqlite3.Row) -> TargetCandidate:
        return TargetCandidate(
            str(row["hit_id"]),
            str(row["group_id"]),
            str(row["canonical_url"]),
            str(row["name"]) if row["name"] is not None else None,
            str(row["source"]),
            int(row["rank"]),
            membership=MembershipState(str(row["membership_state"])),
        )

    @staticmethod
    def _candidate(
        url: str,
        name: str | None,
        source: str,
        rank: int,
        *,
        activity_posts_per_day: int | None = None,
        membership: MembershipState = MembershipState.JOINED,
    ) -> TargetCandidate:
        canonical_url, group_id = TargetPreparationService._normalize_group_url(url)
        candidate_id = str(uuid4())
        return TargetCandidate(
            candidate_id,
            group_id,
            canonical_url,
            name,
            source,
            rank,
            activity_posts_per_day,
            membership,
        )

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
