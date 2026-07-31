"""Unit tests for normal Chrome CDP session attachment."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.session.browser import (
    NormalChromeAttachmentFailure,
    NormalChromeAttachmentTimeout,
    _parse_local_devtools_endpoint,
    collect_normal_chrome_attachment_state,
    launch_normal_chrome_attachment,
)


def test_launch_normal_chrome_uses_scanner_profile_and_loopback_cdp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_directory = tmp_path / "scanner-profile"
    captured: dict[str, object] = {}

    class Process:
        def poll(self) -> None:
            return None

    def popen(arguments: list[str]) -> Process:
        captured["arguments"] = arguments
        return Process()

    monkeypatch.setattr(
        "app.session.browser._resolve_normal_chrome_executable", lambda: Path("chrome.exe")
    )
    monkeypatch.setattr("app.session.browser.Popen", popen)
    monkeypatch.setattr(
        "app.session.browser._wait_for_local_devtools_endpoint",
        lambda *_args, **_kwargs: "http://127.0.0.1:43210",
    )

    launch_normal_chrome_attachment(
        "https://example.test/login",
        user_data_directory=profile_directory,
        timeout_seconds=45,
    )

    assert captured["arguments"] == [
        "chrome.exe",
        f"--user-data-dir={profile_directory}",
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
        "--no-first-run",
        "--no-default-browser-check",
        "https://example.test/login",
    ]


def test_collect_normal_chrome_attaches_to_loopback_cdp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class Context:
        def storage_state(self) -> dict[str, list[object]]:
            return {"cookies": [{"name": "session", "value": "opaque"}], "origins": []}

    class Browser:
        def __init__(self) -> None:
            self.contexts = [Context()]

        def close(self) -> None:
            captured["browser_closed"] = True

    class Chromium:
        def connect_over_cdp(self, endpoint: str) -> Browser:
            captured["endpoint"] = endpoint
            return Browser()

    class Playwright:
        chromium = Chromium()

    class PlaywrightContext:
        def __enter__(self) -> Playwright:
            return Playwright()

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        "app.session.browser._wait_for_local_devtools_endpoint",
        lambda *_args, **_kwargs: "http://127.0.0.1:43210",
    )
    monkeypatch.setattr("app.session.browser.sync_playwright", lambda: PlaywrightContext())

    state = collect_normal_chrome_attachment_state(
        user_data_directory=tmp_path / "scanner-profile",
        timeout_seconds=45,
    )

    assert state == {"cookies": [{"name": "session", "value": "opaque"}], "origins": []}
    assert captured["endpoint"] == "http://127.0.0.1:43210"
    assert captured["browser_closed"] is True


def test_parse_local_devtools_endpoint_rejects_invalid_data() -> None:
    assert (
        _parse_local_devtools_endpoint("43123\n/devtools/browser/opaque\n")
        == "http://127.0.0.1:43123"
    )

    for invalid in ("0\n/path\n", "70000\n/path\n", "not-a-port\n/path\n", "43123\n\n"):
        with pytest.raises(NormalChromeAttachmentFailure):
            _parse_local_devtools_endpoint(invalid)


def test_launch_normal_chrome_maps_a_devtools_timeout_to_typed_terminal_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        def poll(self) -> None:
            return None

    monkeypatch.setattr(
        "app.session.browser._resolve_normal_chrome_executable", lambda: Path("chrome.exe")
    )
    monkeypatch.setattr("app.session.browser.Popen", lambda _arguments: Process())
    monkeypatch.setattr(
        "app.session.browser._wait_for_local_devtools_endpoint",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(NormalChromeAttachmentTimeout("timed out")),
    )

    with pytest.raises(NormalChromeAttachmentTimeout):
        launch_normal_chrome_attachment(
            "https://example.test/login",
            user_data_directory=tmp_path / "scanner-profile",
        )
