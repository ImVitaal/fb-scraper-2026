"""Visible browser collection for guided session preparation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from shutil import copy2, copytree
from tempfile import TemporaryDirectory
from typing import cast

from playwright.sync_api import sync_playwright

from app.session.profiles import SessionEnvelopeError, StorageState


def collect_guided_storage_state(
    start_url: str,
    *,
    continue_prompt: Callable[[str], str] = input,
    channel: str | None = None,
    user_data_directory: Path | None = None,
) -> StorageState:
    """Open a visible browser and capture state after operator-completed login."""
    with sync_playwright() as playwright:
        if user_data_directory is not None:
            user_data_directory.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                str(user_data_directory),
                channel=channel,
                headless=False,
            )
            browser = None
        else:
            browser = playwright.chromium.launch(headless=False, channel=channel)
            context = browser.new_context()
        try:
            try:
                page = context.new_page()
                page.goto(start_url, wait_until="domcontentloaded")
                continue_prompt("Complete sign-in in the visible browser, then press Enter here. ")
                state = context.storage_state()
            finally:
                context.close()
        finally:
            if browser is not None:
                browser.close()
    if not isinstance(state, dict):
        raise SessionEnvelopeError("guided login returned an invalid browser storage state")
    storage_state = cast(StorageState, state)
    if not storage_state.get("cookies") and not storage_state.get("origins"):
        raise SessionEnvelopeError("guided login did not produce an authenticated session")
    return storage_state


def collect_imported_browser_profile_state(
    user_data_directory: Path,
    *,
    profile_name: str = "Default",
    channel: str | None = None,
) -> StorageState:
    """Export state from a temporary copy of one local Chromium profile."""
    if not user_data_directory.is_dir():
        raise ValueError("browser user-data directory does not exist")
    _validate_profile_name(profile_name)
    profile_directory = user_data_directory / profile_name
    local_state = user_data_directory / "Local State"
    if not profile_directory.is_dir() or not local_state.is_file():
        raise ValueError("browser user-data directory lacks the selected profile or Local State")

    with TemporaryDirectory(prefix="pgscan-browser-import-") as temporary:
        staged_root = Path(temporary)
        copy2(local_state, staged_root / "Local State")
        copytree(
            profile_directory,
            staged_root / profile_name,
            ignore=_browser_copy_ignore,
        )
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(staged_root),
                args=[f"--profile-directory={profile_name}"],
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
        if _uses_application_bound_encryption(local_state):
            raise SessionEnvelopeError(
                "copied browser profile uses application-bound encryption; "
                "use the existing visible session login"
            )
        raise SessionEnvelopeError("browser profile did not contain an authenticated session")
    return storage_state


def _browser_copy_ignore(directory: str, names: list[str]) -> set[str]:
    """Skip disposable browser caches while retaining session databases."""
    ignored_names = {
        "Cache",
        "Code Cache",
        "Crashpad",
        "DawnCache",
        "Extensions",
        "GPUCache",
        "GrShaderCache",
        "GraphiteDawnCache",
        "ShaderCache",
        "Sessions",
    }
    ignored = {name for name in names if name in ignored_names}
    if Path(directory).name == "Service Worker":
        ignored.update(name for name in names if name in {"CacheStorage", "ScriptCache"})
    return ignored


def _uses_application_bound_encryption(local_state: Path) -> bool:
    """Detect the Windows profile marker without exposing its encrypted value."""
    try:
        payload = json.loads(local_state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    os_crypt = payload.get("os_crypt")
    return isinstance(os_crypt, dict) and bool(os_crypt.get("app_bound_encrypted_key"))


def _validate_profile_name(profile_name: str) -> None:
    if (
        not profile_name
        or profile_name in {".", ".."}
        or "/" in profile_name
        or "\\" in profile_name
    ):
        raise ValueError("browser profile name is invalid")
