"""One-page Playwright adapter for the supported live Group HTML layout."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from playwright.sync_api import sync_playwright


class PlaywrightGroupCaptureAdapter:
    """Capture rendered Group HTML in a context recreated from an encrypted profile."""

    def __init__(self, storage_state: Mapping[str, object]) -> None:
        self.storage_state = dict(storage_state)

    def capture_group(self, target_url: str) -> bytes:
        """Navigate to a selected Group and return rendered HTML bytes."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(storage_state=cast(Any, self.storage_state))
                try:
                    page = context.new_page()
                    page.goto(target_url, wait_until="domcontentloaded")
                    return page.content().encode("utf-8")
                finally:
                    context.close()
            finally:
                browser.close()
