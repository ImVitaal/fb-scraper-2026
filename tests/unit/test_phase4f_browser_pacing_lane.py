"""Unit coverage for Phase 4F browser pacing and immediate stops."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.capture import (
    BrowserCaptureLimits,
    BrowserStateError,
    PlaywrightGroupCaptureAdapter,
    playwright_adapter,
)


class _FakePage:
    def __init__(self) -> None:
        self.waits: list[float] = []
        self.evaluated: list[str] = []

    def wait_for_timeout(self, milliseconds: float) -> None:
        self.waits.append(milliseconds)

    def evaluate(self, script: str) -> None:
        self.evaluated.append(script)


def _capture(
    limits: BrowserCaptureLimits,
) -> tuple[playwright_adapter._BrowserRenderedPageCapture, _FakePage]:
    page = _FakePage()
    adapter = PlaywrightGroupCaptureAdapter(
        {"cookies": [], "origins": []},
        limits=limits,
    )
    capture = playwright_adapter._BrowserRenderedPageCapture(
        adapter,
        "http://fixture.invalid/group",
        None,
    )
    capture._page = cast(Any, page)
    cast(Any, capture)._raise_if_stop_requested = lambda: None
    return capture, page


def test_browser_limits_define_configurable_pacing_and_retry_delays() -> None:
    limits = BrowserCaptureLimits(
        navigation_delay_seconds=11.0,
        scroll_delay_seconds=7.0,
        expansion_delay_seconds=4.0,
        retry_delays_seconds=(30.0, 120.0),
    )

    assert limits.navigation_delay_seconds == 11.0
    assert limits.scroll_delay_seconds == 7.0
    assert limits.expansion_delay_seconds == 4.0
    assert limits.retry_delays_seconds == (30.0, 120.0)


def test_browser_actions_wait_for_the_configured_kind_of_delay() -> None:
    limits = BrowserCaptureLimits(
        scroll_delay_seconds=0.007,
        expansion_delay_seconds=0.004,
    )
    capture, page = _capture(limits)

    capture._execute(playwright_adapter._Action("scroll", "scroll:1"), replay=True)

    assert page.evaluated
    assert page.waits == [7.0]


def test_post_limit_is_cumulative_across_rendered_pages() -> None:
    limits = BrowserCaptureLimits(max_recent_posts=2)
    capture, _ = _capture(limits)

    first_page = """
        <main>
            <article data-pgscan-post-id="post-1">one</article>
            <article data-pgscan-post-id="post-2">two</article>
        </main>
    """
    second_page = """
        <main>
            <article data-pgscan-post-id="post-3">three</article>
        </main>
    """

    capture._bounded_html(first_page)
    bounded_second_page = capture._bounded_html(second_page).decode()

    assert 'data-pgscan-post-id="post-3"' not in bounded_second_page


def test_failed_operations_use_bounded_retry_delays() -> None:
    limits = BrowserCaptureLimits(
        max_retries=2,
        retry_delays_seconds=(0.03, 0.12),
    )
    capture, page = _capture(limits)
    cast(Any, capture)._raise_if_stop_requested = lambda: None
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise PlaywrightTimeoutError("fixture timeout")

    with pytest.raises(BrowserStateError, match="3 attempt"):
        capture._retry(operation, "navigation_failed")

    assert attempts == 3
    assert page.waits == [30.0, 120.0]


@pytest.mark.parametrize("status", [401, 403, 429])
def test_account_warning_response_stops_before_retry(status: int) -> None:
    limits = BrowserCaptureLimits(max_retries=2, retry_delays_seconds=(30.0, 120.0))
    capture, page = _capture(limits)
    capture._on_response(SimpleNamespace(status=status))
    with pytest.raises(BrowserStateError, match=f"http_{status}"):
        playwright_adapter._BrowserRenderedPageCapture._raise_if_stop_requested(capture)

    assert page.waits == []
    telemetry = cast(Any, capture)._adapter.protection_telemetry
    assert telemetry["retry_count"] == 0
    assert telemetry["retry_waits_seconds"] == []
    assert telemetry["stop_reason"] == f"http_{status}"


def test_failed_operation_reports_retry_telemetry() -> None:
    limits = BrowserCaptureLimits(
        max_retries=2,
        retry_delays_seconds=(0.03, 0.12),
    )
    capture, _ = _capture(limits)

    with pytest.raises(BrowserStateError, match="3 attempt"):
        capture._retry(
            lambda: (_ for _ in ()).throw(PlaywrightTimeoutError("fixture timeout")),
            "navigation_failed",
        )

    telemetry = cast(Any, capture)._adapter.protection_telemetry
    assert telemetry["retry_count"] == 2
    assert telemetry["retry_waits_seconds"] == [0.03, 0.12]
