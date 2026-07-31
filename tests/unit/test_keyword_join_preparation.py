"""Coverage for keyword-discovered Groups awaiting membership preparation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.discovery import AppDiscoveryParser, MembershipState
from app.storage.database import Database
from app.targets.preparation import TargetPreparationError, TargetPreparationService

_DISCOVERY_HTML = b"""
<main role="main">
  <article role="article">
    <a href="https://app.invalid/groups/already-joined/">Garden Community Bristol</a>
    <span>Garden Bristol 3 posts a day</span>
  </article>
  <article role="article">
    <a href="https://app.invalid/groups/join-available/">Bristol Garden Exchange</a>
    <span>Garden Bristol 1 post a day</span>
    <button aria-label="Join Group Bristol Garden Exchange">Join</button>
  </article>
  <article role="article">
    <a href="https://app.invalid/groups/join-requested/">Bristol Garden Volunteers</a>
    <span>Garden Bristol 2 posts a day</span>
    <button aria-label="Cancel request to join group">Requested</button>
  </article>
</main>
"""


def test_live_discovery_retains_join_states_without_making_them_collectible() -> None:
    result = AppDiscoveryParser().parse(
        _DISCOVERY_HTML,
        keyword="garden",
        location="Bristol",
        source_url="https://app.invalid/groups/search/groups/",
    )

    assert [(candidate.group_id, candidate.membership) for candidate in result.candidates] == [
        ("join-available", MembershipState.JOIN_AVAILABLE),
        ("join-requested", MembershipState.JOIN_REQUESTED),
        ("already-joined", MembershipState.JOINED),
    ]
    assert [candidate.group_id for candidate in result.joined_candidates] == ["already-joined"]
    assert [candidate.group_id for candidate in result.membership_preparation_candidates] == [
        "join-available",
        "join-requested",
    ]


def test_target_campaign_persists_membership_preparation_for_one_durable_join(
    tmp_path: Path,
) -> None:
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        database.connection.execute(
            """
            INSERT INTO raw_captures(
                capture_id, sha256, source_url, collected_at, storage_path, byte_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "capture-1",
                "a" * 64,
                "https://app.invalid/groups/search/groups/",
                "2026-07-31T00:00:00+00:00",
                "capture.discovery.html.gz",
                len(_DISCOVERY_HTML),
            ),
        )
        service = TargetPreparationService(database.connection)
        campaign = service.add_live_discovery(
            _DISCOVERY_HTML,
            keyword="garden",
            location="Bristol",
            source_url="https://app.invalid/groups/search/groups/",
            raw_capture_id="capture-1",
        )
        with pytest.raises(TargetPreparationError, match="candidate membership is not confirmed"):
            service.select(
                campaign.campaign_id,
                campaign.membership_preparation_candidates[0].candidate_id,
            )
        persisted = database.connection.execute(
            "SELECT group_id FROM candidate_hits ORDER BY group_id"
        ).fetchall()

    assert [(candidate.group_id, candidate.rank) for candidate in campaign.candidates] == [
        ("already-joined", 3)
    ]
    assert [
        (candidate.group_id, candidate.membership)
        for candidate in campaign.membership_preparation_candidates
    ] == [
        ("join-available", MembershipState.JOIN_AVAILABLE),
        ("join-requested", MembershipState.JOIN_REQUESTED),
    ]
    assert campaign.requires_membership_preparation is True
    assert [row["group_id"] for row in persisted] == [
        "already-joined",
        "join-available",
        "join-requested",
    ]
