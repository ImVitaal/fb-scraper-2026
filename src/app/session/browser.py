"""Visible browser collection for guided session preparation."""

from __future__ import annotations

import json
import os
import signal
from collections.abc import Callable
from pathlib import Path
from shutil import copy2, copytree, which
from subprocess import DEVNULL, Popen, run
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from typing import cast

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.session.profiles import SessionEnvelopeError, StorageState


class NormalChromeAttachmentTimeout(RuntimeError):
    """Raised when normal Chrome does not expose its local CDP endpoint in time."""


class NormalChromeAttachmentFailure(RuntimeError):
    """Raised when normal Chrome cannot provide a valid attached storage state."""


_NORMAL_CHROME_ENDPOINT_FILE = "DevToolsActivePort"
_NORMAL_CHROME_PID_FILE = "pgscan-normal-chrome.pid"


def launch_normal_chrome_attachment(
    start_url: str,
    *,
    user_data_directory: Path,
    channel: str | None = "chrome",
    timeout_seconds: int = 15,
) -> None:
    """Launch scanner-owned normal Chrome and confirm its loopback CDP endpoint."""
    if channel not in {None, "chrome"}:
        raise NormalChromeAttachmentFailure("normal Chrome attachment requires Chrome")
    if timeout_seconds <= 0:
        raise NormalChromeAttachmentFailure("attachment timeout must be positive")
    try:
        user_data_directory.mkdir(parents=True, exist_ok=True)
        _release_scanner_owned_chrome(user_data_directory)
        endpoint_file = user_data_directory / _NORMAL_CHROME_ENDPOINT_FILE
        if endpoint_file.exists():
            endpoint_file.unlink()
    except OSError as error:
        raise NormalChromeAttachmentFailure("normal Chrome profile preparation failed") from error
    chrome = _resolve_normal_chrome_executable()
    try:
        process = Popen(
            [
                str(chrome),
                f"--user-data-dir={user_data_directory}",
                "--remote-debugging-address=127.0.0.1",
                "--remote-debugging-port=0",
                "--no-first-run",
                "--no-default-browser-check",
                start_url,
            ]
        )
    except OSError as error:
        raise NormalChromeAttachmentFailure("normal Chrome did not start") from error
    try:
        _write_scanner_owned_pid(user_data_directory, process.pid)
        _wait_for_local_devtools_endpoint(
            endpoint_file,
            timeout_seconds=timeout_seconds,
            process=process,
        )
    except (NormalChromeAttachmentFailure, NormalChromeAttachmentTimeout, OSError) as error:
        try:
            _terminate_process_tree(process.pid)
        except NormalChromeAttachmentFailure as cleanup_error:
            raise error from cleanup_error
        _remove_scanner_owned_pid(user_data_directory)
        raise


def collect_normal_chrome_attachment_state(
    *,
    user_data_directory: Path,
    timeout_seconds: int = 15,
) -> StorageState:
    """Attach to already launched normal Chrome and return its storage state."""
    if timeout_seconds <= 0:
        raise NormalChromeAttachmentFailure("attachment timeout must be positive")
    try:
        endpoint = _wait_for_local_devtools_endpoint(
            user_data_directory / _NORMAL_CHROME_ENDPOINT_FILE,
            timeout_seconds=timeout_seconds,
        )
        with sync_playwright() as playwright:
            browser = None
            try:
                browser = playwright.chromium.connect_over_cdp(endpoint)
                if not browser.contexts:
                    raise NormalChromeAttachmentFailure("normal Chrome has no browser context")
                state = browser.contexts[0].storage_state()
            finally:
                if browser is not None:
                    browser.close()
    except NormalChromeAttachmentFailure:
        raise
    except (OSError, PlaywrightError) as error:
        raise NormalChromeAttachmentFailure("normal Chrome attachment failed") from error
    finally:
        _release_scanner_owned_chrome(user_data_directory)
    if not isinstance(state, dict):
        raise NormalChromeAttachmentFailure("normal Chrome returned an invalid storage state")
    storage_state = cast(StorageState, state)
    if not storage_state.get("cookies") and not storage_state.get("origins"):
        raise NormalChromeAttachmentFailure(
            "normal Chrome did not produce an authenticated session"
        )
    return storage_state


def _write_scanner_owned_pid(user_data_directory: Path, pid: int) -> None:
    try:
        (user_data_directory / _NORMAL_CHROME_PID_FILE).write_text(str(pid), encoding="ascii")
    except OSError as error:
        raise NormalChromeAttachmentFailure(
            "normal Chrome ownership marker could not be written"
        ) from error


def _read_scanner_owned_pid(user_data_directory: Path) -> int | None:
    marker = user_data_directory / _NORMAL_CHROME_PID_FILE
    if not marker.is_file():
        return None
    try:
        value = marker.read_text(encoding="ascii").strip()
        pid = int(value)
    except (OSError, ValueError) as error:
        raise NormalChromeAttachmentFailure("normal Chrome ownership marker was invalid") from error
    if pid <= 0:
        raise NormalChromeAttachmentFailure("normal Chrome ownership marker was invalid")
    return pid


def _remove_scanner_owned_pid(user_data_directory: Path) -> None:
    try:
        (user_data_directory / _NORMAL_CHROME_PID_FILE).unlink(missing_ok=True)
    except OSError as error:
        raise NormalChromeAttachmentFailure(
            "normal Chrome ownership marker could not be removed"
        ) from error


def _release_scanner_owned_chrome(user_data_directory: Path) -> None:
    pid = _read_scanner_owned_pid(user_data_directory)
    if pid is None:
        return
    _terminate_process_tree(pid)
    _remove_scanner_owned_pid(user_data_directory)
    try:
        (user_data_directory / _NORMAL_CHROME_ENDPOINT_FILE).unlink(missing_ok=True)
    except OSError as error:
        raise NormalChromeAttachmentFailure(
            "normal Chrome endpoint could not be removed"
        ) from error


def _terminate_process_tree(pid: int) -> None:
    """Terminate the scanner-owned Chrome process and its descendants on Windows."""
    try:
        result = run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=DEVNULL,
            stderr=DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError as error:
            raise NormalChromeAttachmentFailure(
                "scanner-owned Chrome could not be stopped"
            ) from error
        return
    except OSError as error:
        raise NormalChromeAttachmentFailure("scanner-owned Chrome could not be stopped") from error
    if result.returncode not in {0, 128}:
        raise NormalChromeAttachmentFailure("scanner-owned Chrome could not be stopped")


def _resolve_normal_chrome_executable() -> Path:
    executable = which("chrome.exe")
    if executable is not None:
        return Path(executable)
    roots = (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMW6432"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    )
    for root in roots:
        if root is None:
            continue
        candidate = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if candidate.is_file():
            return candidate
    raise NormalChromeAttachmentFailure("normal Chrome executable was not found")


def _wait_for_local_devtools_endpoint(
    endpoint_file: Path,
    *,
    timeout_seconds: int,
    process: Popen[bytes] | None = None,
) -> str:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise NormalChromeAttachmentFailure("normal Chrome exited before attachment")
        if endpoint_file.is_file():
            try:
                return _parse_local_devtools_endpoint(endpoint_file.read_text(encoding="utf-8"))
            except OSError as error:
                raise NormalChromeAttachmentFailure(
                    "normal Chrome endpoint was unreadable"
                ) from error
        sleep(0.1)
    raise NormalChromeAttachmentTimeout("normal Chrome attachment timed out")


def _parse_local_devtools_endpoint(value: str) -> str:
    lines = value.splitlines()
    if len(lines) < 2 or not lines[0].isdigit() or not lines[1].startswith("/devtools/browser/"):
        raise NormalChromeAttachmentFailure("normal Chrome endpoint was invalid")
    port = int(lines[0])
    if not 1 <= port <= 65535:
        raise NormalChromeAttachmentFailure("normal Chrome endpoint was invalid")
    return f"http://127.0.0.1:{port}"


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
