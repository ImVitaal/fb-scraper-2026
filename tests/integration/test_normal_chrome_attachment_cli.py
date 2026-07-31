"""CLI integration tests for normal Chrome session attachment."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from app.cli.main import app
from app.session import NormalChromeAttachmentTimeout
from app.session.profiles import StorageState


def test_attach_chrome_starts_scanner_owned_normal_chrome(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def launch_attachment(
        start_url: str,
        *,
        user_data_directory: Path,
        channel: str | None = "chrome",
        timeout_seconds: int = 15,
    ) -> None:
        captured.update(
            {
                "start_url": start_url,
                "user_data_directory": user_data_directory,
                "channel": channel,
                "timeout_seconds": timeout_seconds,
            }
        )

    monkeypatch.setattr("app.cli.main.launch_normal_chrome_attachment", launch_attachment)
    output = tmp_path / "operator-data"
    session_root = tmp_path / "private-sessions"

    result = CliRunner().invoke(
        app,
        [
            "session",
            "attach-chrome",
            "--profile",
            "operator",
            "--start-url",
            "https://example.test/login",
            "--attachment-timeout-seconds",
            "45",
            "--output",
            str(output),
            "--session-root",
            str(session_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "start_url": "https://example.test/login",
        "user_data_directory": session_root / "browser-profiles" / "operator",
        "channel": "chrome",
        "timeout_seconds": 45,
    }
    assert json.loads(result.stdout) == {"state": "awaiting_operator"}


def test_finalize_chrome_persists_redacted_session_metadata(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    state: StorageState = {
        "cookies": [{"name": "session", "value": "normal-chrome-secret"}],
        "origins": [],
    }
    captured: dict[str, object] = {}

    def collect_state(*, user_data_directory: Path, timeout_seconds: int = 15) -> StorageState:
        captured.update(
            {"user_data_directory": user_data_directory, "timeout_seconds": timeout_seconds}
        )
        return state

    monkeypatch.setattr("app.cli.main.collect_normal_chrome_attachment_state", collect_state)
    output = tmp_path / "operator-data"
    session_root = tmp_path / "private-sessions"

    result = CliRunner().invoke(
        app,
        [
            "session",
            "finalize-chrome",
            "--profile",
            "operator",
            "--attachment-timeout-seconds",
            "45",
            "--output",
            str(output),
            "--session-root",
            str(session_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "user_data_directory": session_root / "browser-profiles" / "operator",
        "timeout_seconds": 45,
    }
    payload = json.loads(result.stdout)
    assert payload["state"] == "completed"
    assert payload["metadata"]["profile_id"] == "operator"
    assert payload["metadata"]["session_class"] == "guided_login"
    assert payload["metadata"]["source_browser"] == "normal_chrome_cdp_persistent"
    assert "normal-chrome-secret" not in result.stdout


def test_attach_chrome_reports_a_redacted_timeout(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    def launch_attachment(*_args: object, **_kwargs: object) -> None:
        raise NormalChromeAttachmentTimeout("normal-chrome-secret")

    monkeypatch.setattr("app.cli.main.launch_normal_chrome_attachment", launch_attachment)

    result = CliRunner().invoke(
        app,
        [
            "session",
            "attach-chrome",
            "--profile",
            "operator",
            "--output",
            str(tmp_path / "operator-data"),
            "--session-root",
            str(tmp_path / "private-sessions"),
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"state": "timeout"}
    assert "normal-chrome-secret" not in result.stdout
