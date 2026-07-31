"""Unit coverage for the single checkpointed membership action."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.capture import BrowserStateError
from app.discovery import MembershipJoinAdapter


class _Locator:
    def __init__(self, page: _Page, selector: str) -> None:
        self.page = page
        self.selector = selector

    def count(self) -> int:
        if self.selector.startswith("button"):
            return 0 if self.page.joined else self.page.join_controls
        return 1

    def click(self) -> None:
        self.page.events.append("click")
        self.page.joined = self.page.will_join

    def inner_text(self, *, timeout: float | None = None) -> str:
        del timeout
        return self.page.body


class _Page:
    def __init__(self, *, body: str = "Group", join_controls: int = 1) -> None:
        self.body = body
        self.events: list[str] = []
        self.join_controls = join_controls
        self.joined = False
        self.will_join = True
        self.url = "https://app.invalid/groups/garden"
        self.response_handler: Callable[[Any], None] | None = None

    def on(self, event: str, handler: Callable[[Any], None]) -> None:
        assert event == "response"
        self.response_handler = handler

    def goto(self, url: str, *, wait_until: str) -> object:
        self.events.append(f"goto:{wait_until}:{url}")
        return object()

    def content(self) -> str:
        return "<html>before</html>" if not self.joined else "<html>after</html>"

    def wait_for_timeout(self, timeout: float) -> None:
        self.events.append(f"wait:{timeout}")

    def locator(self, selector: str) -> _Locator:
        return _Locator(self, selector)

    def get_by_role(self, role: str, *, name: str, exact: bool) -> _Locator:
        assert (role, name, exact) == ("button", "Join Group", True)
        self.events.append("join-role-locator")
        return _Locator(self, "button[role='join-group']")


def test_join_checkpoints_before_one_visible_click() -> None:
    page = _Page()
    checkpointed: list[bytes] = []

    def checkpoint(raw: bytes) -> None:
        checkpointed.append(raw)
        page.events.append("checkpoint")

    outcome = MembershipJoinAdapter(navigation_delay_seconds=10, action_delay_seconds=12).join(
        page,
        "https://app.invalid/groups/garden",
        checkpoint_before_action=checkpoint,
    )

    assert checkpointed == [b"<html>before</html>"]
    assert page.events.index("checkpoint") < page.events.index("click")
    assert page.events.count("click") == 1
    assert page.events.count("join-role-locator") == 2
    assert outcome.state == "joined"
    assert outcome.confirmation_html == b"<html>after</html>"


def test_join_does_not_click_when_control_is_ambiguous() -> None:
    page = _Page(join_controls=2)
    with pytest.raises(BrowserStateError, match="join_unavailable"):
        MembershipJoinAdapter(navigation_delay_seconds=0, action_delay_seconds=0).join(
            page,
            "https://app.invalid/groups/garden",
            checkpoint_before_action=lambda raw: None,
        )
    assert "click" not in page.events


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status


class _StoppedPage(_Page):
    def goto(self, url: str, *, wait_until: str) -> object:
        result = super().goto(url, wait_until=wait_until)
        handler = self.response_handler
        assert handler is not None
        handler(_Response(429))
        return result


class _PendingPage(_Page):
    def __init__(self) -> None:
        super().__init__(body="Requested")


class _RejectedPage(_Page):
    def __init__(self) -> None:
        super().__init__()
        self.will_join = False


def test_join_stops_before_click_on_rate_limit_response() -> None:
    page = _StoppedPage()
    with pytest.raises(BrowserStateError, match="http_429"):
        MembershipJoinAdapter(navigation_delay_seconds=0, action_delay_seconds=0).join(
            page,
            "https://app.invalid/groups/garden",
            checkpoint_before_action=lambda raw: None,
        )
    assert "click" not in page.events


def test_join_records_pending_or_rejected_confirmation() -> None:
    adapter = MembershipJoinAdapter(navigation_delay_seconds=0, action_delay_seconds=0)
    pending = adapter.join(
        _PendingPage(),
        "https://app.invalid/groups/garden",
        checkpoint_before_action=lambda raw: None,
    )
    rejected = adapter.join(
        _RejectedPage(),
        "https://app.invalid/groups/garden",
        checkpoint_before_action=lambda raw: None,
    )

    assert pending.state == "pending"
    assert rejected.state == "rejected"
