"""Native Windows operator preflight checks with non-secret output."""

from __future__ import annotations

import json
import os
import platform
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import NamedTemporaryFile

from playwright.sync_api import sync_playwright

from app.session.dpapi import protect_for_current_user, unprotect_for_current_user
from app.storage.database import MIGRATION_PATTERN


@dataclass(frozen=True)
class PreflightCheck:
    """One bounded check result without filesystem or secret values."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class PreflightReport:
    """Complete operator preflight result."""

    checks: tuple[PreflightCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.passed for check in self.checks)

    def by_name(self, name: str) -> PreflightCheck:
        return next(check for check in self.checks if check.name == name)

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "checks": [check.as_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)


@dataclass(frozen=True)
class PreflightDependencies:
    """Injectable system boundaries for deterministic preflight tests."""

    platform_name: Callable[[], str]
    python_version: Callable[[], tuple[int, int, int]]
    package_version: Callable[[], str | None]
    migrations_ready: Callable[[], bool]
    playwright_version: Callable[[], str | None]
    chromium_executable: Callable[[], Path]
    dpapi_round_trip: Callable[[bytes], bytes]


def _package_version() -> str | None:
    try:
        return version("private-group-scanner")
    except PackageNotFoundError:
        return None


def _playwright_version() -> str | None:
    try:
        return version("playwright")
    except PackageNotFoundError:
        return None


def _migrations_ready() -> bool:
    migration_root = Path(__file__).parent / "storage" / "migrations"
    names = sorted(path.name for path in migration_root.glob("*.sql"))
    versions = [
        int(match.group("version"))
        for name in names
        if (match := MIGRATION_PATTERN.fullmatch(name)) is not None
    ]
    return len(versions) == len(names) and versions == list(range(1, len(versions) + 1))


def _chromium_executable() -> Path:
    with sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path)


def _dpapi_round_trip(value: bytes) -> bytes:
    return unprotect_for_current_user(protect_for_current_user(value))


DEFAULT_DEPENDENCIES = PreflightDependencies(
    platform_name=platform.system,
    python_version=lambda: (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    ),
    package_version=_package_version,
    migrations_ready=_migrations_ready,
    playwright_version=_playwright_version,
    chromium_executable=_chromium_executable,
    dpapi_round_trip=_dpapi_round_trip,
)


def _attempt(name: str, action: Callable[[], bool], passed: str, failed: str) -> PreflightCheck:
    try:
        success = action()
    except Exception:
        success = False
    return PreflightCheck(name, success, passed if success else failed)


def _roots_are_writable(roots: Sequence[Path]) -> bool:
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=root, delete=False) as handle:
            path = Path(handle.name)
            handle.write(b"preflight")
            handle.flush()
            os.fsync(handle.fileno())
        path.unlink()
    return True


def _roots_are_external(repository_root: Path, roots: Sequence[Path]) -> bool:
    repository = repository_root.resolve()
    return all(not root.resolve().is_relative_to(repository) for root in roots)


def run_preflight(
    repository_root: Path,
    storage_roots: Sequence[Path],
    *,
    dependencies: PreflightDependencies = DEFAULT_DEPENDENCIES,
) -> PreflightReport:
    """Run all Phase 4A checks and omit concrete root values from output."""
    python = dependencies.python_version()
    checks = (
        PreflightCheck(
            "windows",
            dependencies.platform_name() == "Windows",
            "native Windows" if dependencies.platform_name() == "Windows" else "Windows required",
        ),
        PreflightCheck(
            "python",
            python >= (3, 12, 0),
            f"{python[0]}.{python[1]}.{python[2]}",
        ),
        _attempt(
            "package",
            lambda: dependencies.package_version() is not None,
            "installed",
            "not installed",
        ),
        _attempt(
            "migrations",
            dependencies.migrations_ready,
            "ordered and complete",
            "missing or invalid",
        ),
        _attempt(
            "playwright",
            lambda: dependencies.playwright_version() is not None,
            "installed",
            "not installed",
        ),
        _attempt(
            "chromium",
            lambda: dependencies.chromium_executable().is_file(),
            "installed",
            "not installed",
        ),
        _attempt(
            "dpapi",
            lambda: dependencies.dpapi_round_trip(b"pgscan-preflight") == b"pgscan-preflight",
            "current-user round trip passed",
            "current-user round trip failed",
        ),
        _attempt(
            "writable_roots",
            lambda: _roots_are_writable(storage_roots),
            "all roots writable",
            "one or more roots not writable",
        ),
        PreflightCheck(
            "external_roots",
            _roots_are_external(repository_root, storage_roots),
            (
                "all roots outside repository"
                if _roots_are_external(repository_root, storage_roots)
                else "one or more roots inside repository"
            ),
        ),
    )
    return PreflightReport(checks)
