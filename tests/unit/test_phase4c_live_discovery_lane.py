"""Phase 4C tests for explicit live and fixture discovery capture."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.discovery.live import (
    AppDiscoveryParser,
    DiscoveryMode,
    MembershipState,
    SessionDiscoveryAdapter,
)
from app.discovery.parser import UnsupportedDiscoveryLayoutError

FIXTURE = Path(__file__).parents[1] / "fixtures" / "app_operator_redacted" / "discovery.html"


class FakePage:
    """Minimal synchronous Playwright page test double."""

    def __init__(self, html: str) -> None:
        self.html = html
        self.visited: list[tuple[str, str]] = []

    def goto(self, url: str, *, wait_until: str) -> None:
        self.visited.append((url, wait_until))

    def content(self) -> str:
        return self.html


def test_live_adapter_captures_query_page_for_raw_first_persistence_then_parsing() -> None:
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
    assert capture.mode is DiscoveryMode.LIVE
    assert [(item.group_id, item.rank) for item in result.candidates] == [
        ("9400001", 1),
        ("9400002", 2),
    ]
    assert result.candidates[0].matching_evidence == ("keyword:garden", "location:Bristol")


def test_fixture_mode_is_explicit_and_live_layout_failures_return_no_candidates() -> None:
    capture = SessionDiscoveryAdapter(mode=DiscoveryMode.FIXTURE).capture(
        keyword="garden",
        location="Bristol",
        fixture=FIXTURE,
    )
    assert capture.mode is DiscoveryMode.FIXTURE

    with pytest.raises(UnsupportedDiscoveryLayoutError, match="Group candidates"):
        AppDiscoveryParser().parse(
            b"<main role='main'>REDACTED</main>",
            keyword="garden",
            location="Bristol",
            source_url="https://app.invalid/groups/search/groups/",
        )


def test_live_discovery_surfaces_membership_preparation_candidates() -> None:
    html = b"""
    <main role="main"><article>
      <a href="https://app.invalid/groups/9400001/">Garden Community Bristol</a>
      <button aria-label="Join Group Garden Community Bristol">Join</button>
    </article></main>
    """

    result = AppDiscoveryParser().parse(
        html,
        keyword="garden",
        location="Bristol",
        source_url="https://app.invalid/groups/search/groups/",
    )

    assert result.joined_candidates == ()
    assert result.membership_preparation_candidates[0].membership is MembershipState.JOIN_AVAILABLE


def test_discovery_modes_reject_implicit_or_mixed_transports() -> None:
    with pytest.raises(ValueError, match="base_url"):
        SessionDiscoveryAdapter(mode=DiscoveryMode.LIVE)
    with pytest.raises(ValueError, match="does not accept base_url"):
        SessionDiscoveryAdapter(mode=DiscoveryMode.FIXTURE, base_url="https://app.invalid")
    with pytest.raises(ValueError, match="requires only fixture"):
        SessionDiscoveryAdapter(mode=DiscoveryMode.FIXTURE).capture(
            keyword="garden",
            location="Bristol",
        )
    with pytest.raises(ValueError, match="requires only page"):
        SessionDiscoveryAdapter(
            mode=DiscoveryMode.LIVE,
            base_url="https://app.invalid",
        ).capture(
            keyword="garden",
            location="Bristol",
            fixture=FIXTURE,
        )
