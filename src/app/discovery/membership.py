"""One visible, checkpointed membership action for a keyword-selected Group."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.capture import BrowserStateError


@dataclass(frozen=True)
class MembershipJoinOutcome:
    """Non-secret browser evidence from one membership action."""

    before_html: bytes
    confirmation_html: bytes
    state: str


class MembershipJoinAdapter:
    """Perform one confirmed Join action without retries."""

    def __init__(self, *, navigation_delay_seconds: float, action_delay_seconds: float) -> None:
        self.navigation_delay_seconds = navigation_delay_seconds
        self.action_delay_seconds = action_delay_seconds

    def join(
        self,
        page: Any,
        target_url: str,
        *,
        checkpoint_before_action: Callable[[bytes], None],
    ) -> MembershipJoinOutcome:
        """Navigate, persist the pre-action page, then make one visible Join click."""
        stop_reason: str | None = None

        def observe_response(response: Any) -> None:
            nonlocal stop_reason
            if getattr(response, "status", None) in {401, 403, 429}:
                stop_reason = f"http_{response.status}"

        page.on("response", observe_response)
        page.goto(target_url, wait_until="domcontentloaded")
        page.wait_for_timeout(self.navigation_delay_seconds * 1000)
        self._raise_if_stopped(page, stop_reason)
        before_html = page.content().encode("utf-8")
        join_button = page.get_by_role("button", name="Join Group", exact=True)
        count = join_button.count()
        if count != 1:
            raise BrowserStateError("join_unavailable", "expected exactly one visible Join control")
        checkpoint_before_action(before_html)
        page.wait_for_timeout(self.action_delay_seconds * 1000)
        self._raise_if_stopped(page, stop_reason)
        join_button.click()
        page.wait_for_timeout(self.action_delay_seconds * 1000)
        self._raise_if_stopped(page, stop_reason)
        confirmation_html = page.content().encode("utf-8")
        body = page.locator("body").inner_text(timeout=1_000).casefold()
        if "cancel request" in body or "requested" in body:
            state = "pending"
        elif page.get_by_role("button", name="Join Group", exact=True).count() == 0:
            state = "joined"
        else:
            state = "rejected"
        return MembershipJoinOutcome(before_html, confirmation_html, state)

    @staticmethod
    def _raise_if_stopped(page: Any, stop_reason: str | None) -> None:
        if stop_reason is not None:
            raise BrowserStateError(stop_reason, "membership action reached an account-stop state")
        url = str(page.url).casefold()
        body = page.locator("body").inner_text(timeout=1_000).casefold()
        conditions = (
            ("login_required", ("/login",), ("log in", "login")),
            ("challenge", ("/challenge", "/checkpoint", "/captcha"), ("captcha", "checkpoint")),
            (
                "restricted",
                ("/restricted", "/locked"),
                ("account restricted", "account locked", "temporarily blocked"),
            ),
        )
        for failure, paths, text in conditions:
            if any(value in url for value in paths) or any(value in body for value in text):
                raise BrowserStateError(failure, "membership action reached an account-stop state")
