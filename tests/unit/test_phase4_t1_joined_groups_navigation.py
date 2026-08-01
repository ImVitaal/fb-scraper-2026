"""T1 regression coverage for authenticated joined-Group discovery navigation."""

from __future__ import annotations

from pathlib import Path

from app.discovery import (
    AppDiscoveryParser,
    DiscoveryMode,
    MembershipState,
    SessionDiscoveryAdapter,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "app_operator_redacted"
    / "t1_current_rendered_discovery.html"
)


class FakePage:
    """Minimal synchronous page double that retains navigation calls only."""

    def __init__(self, html: str) -> None:
        self.html = html
        self.visited: list[tuple[str, str]] = []

    def goto(self, url: str, *, wait_until: str) -> None:
        self.visited.append((url, wait_until))

    def content(self) -> str:
        return self.html


def test_live_discovery_uses_joined_groups_route_and_preserves_filtering_contract() -> None:
    page = FakePage(FIXTURE.read_text(encoding="utf-8"))
    adapter = SessionDiscoveryAdapter(
        mode=DiscoveryMode.LIVE,
        base_url="https://app.invalid",
    )

    capture = adapter.capture(keyword="garden", location="Bristol", page=page)
    result = AppDiscoveryParser().parse(
        capture.raw_html,
        keyword="garden",
        location="Bristol",
        source_url=capture.source_url,
    )

    assert page.visited == [
        (
            "https://app.invalid/groups/?q=garden+Bristol&location=Bristol",
            "domcontentloaded",
        )
    ]
    assert capture.raw_html == FIXTURE.read_bytes()
    assert result.keyword == "garden"
    assert result.location == "Bristol"
    assert {
        candidate.group_id: (
            candidate.canonical_url,
            candidate.membership,
        )
        for candidate in result.candidates
    } == {
        "t1-joined-001": (
            "https://app.invalid/groups/t1-joined-001",
            MembershipState.JOINED,
        ),
        "t1-join-002": (
            "https://app.invalid/groups/t1-join-002",
            MembershipState.JOIN_AVAILABLE,
        ),
        "t1-requested-003": (
            "https://app.invalid/groups/t1-requested-003",
            MembershipState.JOIN_REQUESTED,
        ),
    }
    joined = next(
        candidate for candidate in result.candidates if candidate.group_id == "t1-joined-001"
    )
    assert joined.matching_evidence == ("keyword:garden", "location:Bristol")
    assert joined.activity_posts_per_day == 12
    assert [candidate.group_id for candidate in result.joined_candidates] == ["t1-joined-001"]
    assert [candidate.group_id for candidate in result.membership_preparation_candidates] == [
        "t1-join-002",
        "t1-requested-003",
    ]
