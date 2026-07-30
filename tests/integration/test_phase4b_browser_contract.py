"""Real-browser acceptance tests for the Phase 4B capture contract."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.capture.playwright_adapter import (
    BrowserCaptureLimits,
    BrowserStateError,
    CaptureBoundExceeded,
    PlaywrightGroupCaptureAdapter,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "phase4b_browser"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def _fixture_server() -> Iterator[str]:
    handler = lambda *args, **kwargs: _QuietHandler(  # noqa: E731
        *args, directory=str(FIXTURES), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _collect(adapter: PlaywrightGroupCaptureAdapter, url: str) -> tuple[list[bytes], list[str]]:
    raw_pages: list[bytes] = []
    events: list[str] = []
    cursor: str | None = None
    with adapter.capture_pages(
        url,
        lower_bound=datetime(2026, 6, 30, tzinfo=UTC),
    ) as capture:
        while True:
            page = capture(cursor)
            raw_pages.append(page.raw_html)
            events.append("persist")
            if page.next_cursor is None:
                break
            assert events[-1] == "persist"
            cursor = page.next_cursor
            events.append("action")
    assert adapter.closed
    return raw_pages, events


@pytest.mark.integration
def test_real_browser_keeps_one_context_and_checkpoints_before_each_action() -> None:
    with _fixture_server() as base_url:
        adapter = PlaywrightGroupCaptureAdapter(
            {"cookies": [], "origins": []},
            limits=BrowserCaptureLimits(max_pages=8, max_interactions=7),
        )
        raw_pages, events = _collect(adapter, f"{base_url}/dynamic_group.html")

    final_html = raw_pages[-1].decode()
    assert len(raw_pages) == 4
    assert events == [
        "persist",
        "action",
        "persist",
        "action",
        "persist",
        "action",
        "persist",
    ]
    assert "Expanded post body" in final_html
    assert "First top-level comment" in final_html
    assert "Old boundary post" in final_html
    assert "View 3 replies" in final_html


@pytest.mark.integration
def test_interrupted_browser_capture_resumes_from_opaque_next_action() -> None:
    with _fixture_server() as base_url:
        url = f"{base_url}/dynamic_group.html"
        interrupted = PlaywrightGroupCaptureAdapter({"cookies": [], "origins": []})
        with (
            pytest.raises(KeyboardInterrupt),
            interrupted.capture_pages(
                url,
                lower_bound=datetime(2026, 6, 30, tzinfo=UTC),
            ) as capture,
        ):
            first = capture(None)
            assert first.next_cursor is not None
            second = capture(first.next_cursor)
            assert second.next_cursor is not None
            durable_cursor = second.next_cursor
            raise KeyboardInterrupt
        assert interrupted.closed

        resumed = PlaywrightGroupCaptureAdapter({"cookies": [], "origins": []})
        with resumed.capture_pages(
            url,
            lower_bound=datetime(2026, 6, 30, tzinfo=UTC),
        ) as capture:
            page = capture(durable_cursor)
            while page.next_cursor is not None:
                page = capture(page.next_cursor)
        resumed_final = page.raw_html

        uninterrupted = PlaywrightGroupCaptureAdapter({"cookies": [], "origins": []})
        uninterrupted_pages, _ = _collect(uninterrupted, url)

    assert resumed.closed
    assert resumed_final == uninterrupted_pages[-1]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("fixture_state", "failure_class"),
    [
        ("login", "login_required"),
        ("challenge", "challenge"),
        ("restricted", "restricted"),
        ("unavailable", "group_unavailable"),
        ("drift", "layout_drift"),
    ],
)
def test_browser_failure_pages_are_explicit_non_success_states(
    fixture_state: str,
    failure_class: str,
) -> None:
    with _fixture_server() as base_url:
        adapter = PlaywrightGroupCaptureAdapter({"cookies": [], "origins": []})
        url = f"{base_url}/failure.html?state={fixture_state}"
        with (
            pytest.raises(BrowserStateError) as caught,
            adapter.capture_pages(url) as capture,
        ):
            capture(None)

    assert caught.value.failure_class == failure_class
    assert adapter.closed


@pytest.mark.integration
def test_browser_page_interaction_time_and_storage_bounds_are_explicit() -> None:
    with _fixture_server() as base_url:
        url = f"{base_url}/dynamic_group.html"
        page_limited = PlaywrightGroupCaptureAdapter(
            {"cookies": [], "origins": []},
            limits=BrowserCaptureLimits(max_pages=1),
        )
        with (
            pytest.raises(CaptureBoundExceeded, match="page_limit"),
            page_limited.capture_pages(url) as capture,
        ):
            first = capture(None)
            capture(first.next_cursor)

        storage_limited = PlaywrightGroupCaptureAdapter(
            {"cookies": [], "origins": []},
            limits=BrowserCaptureLimits(max_storage_bytes=32),
        )
        with (
            pytest.raises(CaptureBoundExceeded, match="storage_limit"),
            storage_limited.capture_pages(url) as capture,
        ):
            capture(None)

        interaction_limited = PlaywrightGroupCaptureAdapter(
            {"cookies": [], "origins": []},
            limits=BrowserCaptureLimits(max_interactions=1),
        )
        with (
            pytest.raises(CaptureBoundExceeded, match="interaction_limit"),
            interaction_limited.capture_pages(url) as capture,
        ):
            first = capture(None)
            second = capture(first.next_cursor)
            capture(second.next_cursor)

        time_limited = PlaywrightGroupCaptureAdapter(
            {"cookies": [], "origins": []},
            limits=BrowserCaptureLimits(max_seconds=0.000001),
        )
        with (
            pytest.raises(CaptureBoundExceeded, match="time_limit"),
            time_limited.capture_pages(url) as capture,
        ):
            capture(None)


@pytest.mark.integration
def test_navigation_retries_stop_at_the_configured_bound() -> None:
    adapter = PlaywrightGroupCaptureAdapter(
        {"cookies": [], "origins": []},
        limits=BrowserCaptureLimits(
            max_retries=1,
            navigation_timeout_ms=100,
        ),
    )
    with (
        pytest.raises(BrowserStateError, match=r"navigation_failed:.*2 attempt"),
        adapter.capture_pages("http://127.0.0.1:1/unreachable") as capture,
    ):
        capture(None)

    assert adapter.closed
