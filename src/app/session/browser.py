"""Visible browser collection for guided session preparation."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from playwright.sync_api import sync_playwright

from app.session.profiles import SessionEnvelopeError, StorageState


def collect_guided_storage_state(
    start_url: str,
    *,
    continue_prompt: Callable[[str], str] = input,
) -> StorageState:
    """Open a visible browser and capture state after operator-completed login."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            try:
                page = context.new_page()
                page.goto(start_url, wait_until="domcontentloaded")
                continue_prompt("Complete sign-in in the visible browser, then press Enter here. ")
                state = context.storage_state()
            finally:
                context.close()
        finally:
            browser.close()
    if not isinstance(state, dict):
        raise SessionEnvelopeError("guided login returned an invalid browser storage state")
    storage_state = cast(StorageState, state)
    if not storage_state.get("cookies") and not storage_state.get("origins"):
        raise SessionEnvelopeError("guided login did not produce an authenticated session")
    return storage_state
