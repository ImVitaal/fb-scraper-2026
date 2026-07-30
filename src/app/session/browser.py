"""Visible browser collection for guided session preparation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
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


def collect_imported_browser_profile_state(
    profile_directory: Path,
    *,
    channel: str | None = None,
) -> StorageState:
    """Export state from one operator-selected local Chromium profile directory."""
    if not profile_directory.is_dir():
        raise ValueError("browser profile directory does not exist")
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_directory),
            channel=channel,
            headless=True,
        )
        try:
            state = context.storage_state()
        finally:
            context.close()
    if not isinstance(state, dict):
        raise SessionEnvelopeError("browser profile returned an invalid storage state")
    storage_state = cast(StorageState, state)
    if not storage_state.get("cookies") and not storage_state.get("origins"):
        raise SessionEnvelopeError("browser profile did not contain an authenticated session")
    return storage_state
