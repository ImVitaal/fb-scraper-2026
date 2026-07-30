"""Phase 4F protection coverage for account-bound live discovery."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.capture import BrowserStateError
from app.discovery.live import DiscoveryMode, SessionDiscoveryAdapter


class _Locator:
    def __init__(self, count: int = 0, text: str = "") -> None:
        self._count = count
        self._text = text

    def count(self) -> int:
        return self._count

    def inner_text(self, *, timeout: int) -> str:
        del timeout
        return self._text


class _ProtectedPage:
    def __init__(
        self,
        *,
        failures: int = 0,
        response_status: int | None = None,
        body: str = "",
        url: str = "https://app.invalid/groups/search/groups/",
    ) -> None:
        self.failures = failures
        self.response_status = response_status
        self.body = body
        self.url = url
        self.goto_count = 0
        self.waits: list[float] = []
        self._response_handler: Callable[[object], None] | None = None

    def on(self, event: str, handler: Callable[[object], None]) -> None:
        assert event == "response"
        self._response_handler = handler

    def goto(self, url: str, *, wait_until: str) -> None:
        del url, wait_until
        self.goto_count += 1
        if self.response_status is not None and self._response_handler is not None:
            self._response_handler(SimpleNamespace(status=self.response_status))
        if self.goto_count <= self.failures:
            raise PlaywrightTimeoutError("fixture timeout")

    def wait_for_timeout(self, milliseconds: float) -> None:
        self.waits.append(milliseconds)

    def locator(self, selector: str) -> _Locator:
        body = self.body if self.goto_count else ""
        if selector == "body":
            return _Locator(text=body)
        if selector == "[data-pgscan-login-required], form input[type='password']":
            return _Locator(count=int("login marker" in body.casefold()))
        return _Locator()

    def content(self) -> str:
        return "<main role='main'>fixture</main>"


def _adapter(
    *,
    navigation_delay_seconds: float = 0.0,
    retry_delays_seconds: tuple[float, ...] = (),
    max_retries: int = 0,
) -> SessionDiscoveryAdapter:
    return SessionDiscoveryAdapter(
        mode=DiscoveryMode.LIVE,
        base_url="https://app.invalid",
        navigation_delay_seconds=navigation_delay_seconds,
        retry_delays_seconds=retry_delays_seconds,
        max_retries=max_retries,
    )


def test_live_discovery_waits_after_navigation_and_reports_telemetry() -> None:
    page = _ProtectedPage()
    adapter = _adapter(navigation_delay_seconds=0.011)

    capture = adapter.capture(keyword="garden", location="London", page=page)

    assert page.waits == [11.0]
    assert capture.protection == {
        "delays_seconds": {"navigation": 0.011},
        "retry_count": 0,
        "retry_waits_seconds": [],
        "stop_reason": None,
    }


def test_live_discovery_retries_transient_navigation_twice_with_bounded_delays() -> None:
    page = _ProtectedPage(failures=2)
    adapter = _adapter(
        max_retries=2,
        retry_delays_seconds=(0.03, 0.12),
    )

    capture = adapter.capture(keyword="garden", location="London", page=page)

    assert page.goto_count == 3
    assert page.waits == [30.0, 120.0]
    assert capture.protection["retry_count"] == 2
    assert capture.protection["retry_waits_seconds"] == [0.03, 0.12]


@pytest.mark.parametrize(
    ("response_status", "body", "expected"),
    [
        (401, "", "http_401"),
        (403, "", "http_403"),
        (429, "", "http_429"),
        (None, "Checkpoint CAPTCHA", "challenge"),
        (None, "Account locked", "restricted"),
        (None, "Login marker", "login_required"),
    ],
)
def test_live_discovery_warning_stops_without_retry(
    response_status: int | None,
    body: str,
    expected: str,
) -> None:
    page = _ProtectedPage(response_status=response_status, body=body)
    adapter = _adapter(
        navigation_delay_seconds=0.011,
        max_retries=2,
        retry_delays_seconds=(0.03, 0.12),
    )

    with pytest.raises(BrowserStateError, match=expected):
        adapter.capture(keyword="garden", location="London", page=page)

    assert page.goto_count == 1
    assert page.waits == []
    assert adapter.protection_telemetry["retry_count"] == 0
    assert adapter.protection_telemetry["stop_reason"] == expected
    assert "app.invalid" not in repr(adapter.protection_telemetry)
