"""Unit coverage for bounded empty Group shell progress stops."""

from __future__ import annotations

from typing import Any, cast

import pytest

from app.capture import (
    BrowserCaptureLimits,
    BrowserStateError,
    PlaywrightGroupCaptureAdapter,
    playwright_adapter,
)

EMPTY_GROUP_SHELL = b"""
<main data-pgscan-content-ready="true">
  <a href="/groups/fixture-group">Fixture Group</a>
</main>
"""

POST_BEARING_PAGE = b"""
<main data-pgscan-content-ready="true">
  <div role="article">
    <a href="/groups/fixture-group/posts/fixture-post">Fixture post</a>
    <time datetime="2026-08-01T12:00:00Z">today</time>
  </div>
</main>
"""


class _FakePage:
    def __init__(self, raw_html: bytes) -> None:
        self.raw_html = raw_html

    def content(self) -> str:
        return self.raw_html.decode()


def _capture(
    raw_html: bytes,
    *,
    max_empty_group_shell_pages: int = 3,
    known_post_ids: set[str] | None = None,
) -> tuple[playwright_adapter._BrowserRenderedPageCapture, PlaywrightGroupCaptureAdapter]:
    adapter = PlaywrightGroupCaptureAdapter(
        {"cookies": [], "origins": []},
        limits=BrowserCaptureLimits(
            max_empty_group_shell_pages=max_empty_group_shell_pages,
        ),
        known_post_ids=known_post_ids,
    )
    capture = playwright_adapter._BrowserRenderedPageCapture(
        adapter,
        "https://app.invalid/groups/fixture-group",
        None,
    )
    capture._page = cast(Any, _FakePage(raw_html))
    cast(Any, capture)._wait_for_supported_state = lambda: None
    cast(Any, capture)._perform_checkpointed_action = lambda checkpoint: None
    cast(Any, capture)._derive_next_action = lambda: playwright_adapter._Action(
        "scroll",
        f"scroll:{capture._page_count + 1}",
    )
    return capture, adapter


def test_first_empty_group_shell_is_returned_with_a_checkpoint() -> None:
    capture, adapter = _capture(EMPTY_GROUP_SHELL)

    page = capture(None)

    assert page.raw_html
    assert page.next_cursor is not None
    assert adapter.protection_telemetry["stop_reason"] is None


def test_repeated_empty_group_shell_raises_and_records_stop_reason() -> None:
    capture, adapter = _capture(EMPTY_GROUP_SHELL, max_empty_group_shell_pages=3)

    first = capture(None)
    second = capture(first.next_cursor)

    with pytest.raises(BrowserStateError) as caught:
        capture(second.next_cursor)

    assert caught.value.failure_class == "empty_group_shell_no_post_progress"
    assert adapter.protection_telemetry["stop_reason"] == ("empty_group_shell_no_post_progress")


def test_post_bearing_pages_do_not_trigger_empty_shell_stop() -> None:
    capture, adapter = _capture(
        POST_BEARING_PAGE,
        max_empty_group_shell_pages=2,
        known_post_ids={"fixture-post"},
    )

    cursor = None
    for _ in range(4):
        page = capture(cursor)
        cursor = page.next_cursor

    assert adapter.protection_telemetry["stop_reason"] is None
