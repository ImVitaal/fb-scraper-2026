"""Coverage for discovery through a scanner-owned persistent browser profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from app.cli.main import _prepare_target
from app.configuration import OperatorTargetConfiguration
from app.session import SessionProfileService
from app.storage.database import Database
from app.storage.repositories import RawCaptureMetadataRepository
from app.targets import TargetPreparationService

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "app_operator_redacted"
    / "t1_current_rendered_discovery.html"
)


class _Page:
    def __init__(self, html: str) -> None:
        self.html = html
        self.visited: list[str] = []

    def goto(self, url: str, *, wait_until: str) -> None:
        self.visited.append(url)

    def content(self) -> str:
        return self.html


class _Context:
    def __init__(self, page: _Page) -> None:
        self.page = page
        self.closed = False

    def new_page(self) -> _Page:
        return self.page

    def close(self) -> None:
        self.closed = True


class _Chromium:
    def __init__(self, context: _Context) -> None:
        self.context = context
        self.persistent_calls: list[dict[str, Any]] = []

    def launch_persistent_context(self, user_data_directory: str, **kwargs: Any) -> _Context:
        self.persistent_calls.append({"user_data_directory": user_data_directory, **kwargs})
        return self.context

    def launch(self, **_: Any) -> None:
        raise AssertionError("persistent discovery must not launch a temporary browser")


class _Playwright:
    def __init__(self, chromium: _Chromium) -> None:
        self.chromium = chromium


class _PlaywrightManager:
    def __init__(self, playwright: _Playwright) -> None:
        self.playwright = playwright

    def __enter__(self) -> _Playwright:
        return self.playwright

    def __exit__(self, *_: object) -> None:
        pass


def test_live_discovery_reuses_persistent_profile_for_normal_chrome_session(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    page = _Page(FIXTURE.read_text(encoding="utf-8"))
    context = _Context(page)
    chromium = _Chromium(context)
    monkeypatch.setattr(
        "app.cli.main.sync_playwright",
        lambda: _PlaywrightManager(_Playwright(chromium)),
    )

    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        sessions = SessionProfileService(database.connection, session_root)
        sessions.import_state(
            "persistent-profile",
            {"cookies": [], "origins": []},
            source_browser="normal_chrome_cdp_persistent",
        )
        profile = sessions.browser_profile_directory("persistent-profile")
        selected = _prepare_target(
            TargetPreparationService(database.connection),
            sessions.read_state("persistent-profile"),
            OperatorTargetConfiguration(
                method="live_discovery",
                base_url="https://app.invalid",
                keyword="garden",
                location="Bristol",
                select="t1-joined-001",
            ),
            raw_root=raw_root,
            raw_captures=RawCaptureMetadataRepository(database.connection),
            browser_profile=profile,
            browser_channel="chrome",
        )

    assert selected.group_id == "t1-joined-001"
    assert page.visited == ["https://app.invalid/groups/?q=garden+Bristol&location=Bristol"]
    assert chromium.persistent_calls == [
        {"user_data_directory": str(profile), "channel": "chrome", "headless": False}
    ]
    assert context.closed
    assert len(list(raw_root.glob("*.discovery.html.gz"))) == 1
