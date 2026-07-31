"""Durable state transition coverage for one candidate membership action."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.discovery import MembershipState
from app.storage.database import Database
from app.targets.preparation import TargetPreparationError, TargetPreparationService


def test_join_transition_unlocks_only_a_confirmed_candidate(tmp_path: Path) -> None:
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        database.connection.execute(
            """
            INSERT INTO raw_captures(
                capture_id, sha256, source_url, collected_at, storage_path, byte_count
            ) VALUES (
                'raw', ?, 'https://app.invalid/groups/search/groups/',
                '2026-07-31T00:00:00+00:00', 'raw.discovery.html.gz', 1
            )
            """,
            ("a" * 64,),
        )
        service = TargetPreparationService(database.connection)
        campaign = service.add_live_discovery(
            (
                b"<main><article role='article'><a href='/groups/garden/'>Garden Bristol</a>"
                b"<button aria-label='Join Group'>Join</button><span>1 post a day</span>"
                b"</article></main>"
            ),
            keyword="garden",
            location="Bristol",
            source_url="https://app.invalid/groups/search/groups/",
            raw_capture_id="raw",
        )
        candidate = campaign.membership_preparation_candidates[0]
        service.plan_join(
            campaign.campaign_id, candidate.candidate_id, telemetry={"action": "join_requested"}
        )
        with pytest.raises(TargetPreparationError, match="membership is not confirmed"):
            service.select(campaign.campaign_id, candidate.candidate_id)
        completed = service.complete_join(
            campaign.campaign_id,
            candidate.candidate_id,
            state="joined",
            confirmation_capture_id=None,
            telemetry={"action": "join_requested", "transition_state": "joined"},
        )
        selected = service.select(campaign.campaign_id, completed.candidate_id)

    assert completed.membership is MembershipState.JOINED
    assert selected.group_id == "garden"


@pytest.mark.parametrize("state", ["rejected", "stopped"])
def test_completed_join_identity_is_never_reused_across_campaigns(
    tmp_path: Path, state: str
) -> None:
    """Every terminal join outcome keeps the Group outside later action budgets."""
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        service = TargetPreparationService(database.connection)
        database.connection.execute(
            """
            INSERT INTO raw_captures(
                capture_id, sha256, source_url, collected_at, storage_path, byte_count
            ) VALUES ('raw', ?, 'https://app.invalid/groups/search/groups/',
                      '2026-07-31T00:00:00+00:00', 'raw.discovery.html.gz', 1)
            """,
            ("a" * 64,),
        )
        campaign = service.add_live_discovery(
            b"<main><article role='article'><a href='/groups/garden/'>Garden Bristol</a>"
            b"<button aria-label='Join Group'>Join</button></article></main>",
            keyword="garden",
            location="Bristol",
            source_url="https://app.invalid/groups/search/groups/",
            raw_capture_id="raw",
        )
        candidate = campaign.membership_preparation_candidates[0]
        service.plan_join(campaign.campaign_id, candidate.candidate_id, telemetry={})
        service.complete_join(
            campaign.campaign_id,
            candidate.candidate_id,
            state=state,
            confirmation_capture_id=None,
            telemetry={},
        )

        assert service.attempted_join_group_ids() == {"garden"}
