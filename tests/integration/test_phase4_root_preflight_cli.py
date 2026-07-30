"""Root integration tests for Phase 4 preflight and session-health commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli.main import app
from app.session import SessionProfileService
from app.storage.database import Database


def test_doctor_reports_ready_without_printing_storage_roots(tmp_path: Path) -> None:
    roots = [tmp_path / name for name in ("output-private", "raw-private", "sessions-private")]

    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--output",
            str(roots[0]),
            "--raw-root",
            str(roots[1]),
            "--session-root",
            str(roots[2]),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ready"] is True
    assert {check["name"] for check in payload["checks"]} == {
        "windows",
        "python",
        "package",
        "migrations",
        "playwright",
        "chromium",
        "dpapi",
        "writable_roots",
        "external_roots",
    }
    assert all(str(root) not in result.stdout for root in roots)


def test_session_health_command_classifies_ready_without_printing_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "output"
    session_root = tmp_path / "sessions"
    secret = "session-value-not-for-output"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "operator",
            {"cookies": [{"name": "session", "value": secret}], "origins": []},
        )

    monkeypatch.setattr(
        "app.cli.main.probe_with_playwright",
        lambda route, state: __import__(
            "app.session.health", fromlist=["ProbeObservation"]
        ).ProbeObservation(200, "/home", "authenticated"),
    )
    result = CliRunner().invoke(
        app,
        [
            "session",
            "health",
            "--profile",
            "operator",
            "--probe-url",
            "https://example.test/home",
            "--output",
            str(output),
            "--session-root",
            str(session_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "evidence": ["authenticated_route_reached"],
        "health": "ready",
    }
    assert secret not in result.stdout


def test_import_browser_encrypts_profile_state_without_printing_secrets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    browser_profile = tmp_path / "browser-profile"
    browser_profile.mkdir()
    secret = "imported-browser-secret"
    monkeypatch.setattr(
        "app.cli.main.collect_imported_browser_profile_state",
        lambda directory, channel=None: {
            "cookies": [{"name": "session", "value": secret}],
            "origins": [],
        },
    )

    result = CliRunner().invoke(
        app,
        [
            "session",
            "import-browser",
            "--profile",
            "local-chromium",
            "--browser-profile",
            str(browser_profile),
            "--channel",
            "chrome",
            "--output",
            str(tmp_path / "output"),
            "--session-root",
            str(tmp_path / "sessions"),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["session_class"] == "imported"
    assert payload["source_browser"] == "chrome"
    assert secret not in result.stdout
