"""CLI tests for session import and safe metadata inspection."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from app.cli.main import app


def test_session_import_and_inspect_emit_non_secret_metadata(tmp_path: Path) -> None:
    state = {
        "cookies": [
            {"name": "session_cookie", "value": "fixture-secret", "domain": "example.test"}
        ],
        "origins": [{"origin": "https://example.test", "localStorage": []}],
    }
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    output = tmp_path / "operator-data"
    session_root = tmp_path / "private-sessions"
    runner = CliRunner()

    imported = runner.invoke(
        app,
        [
            "session",
            "import",
            "--profile",
            "profile-cli",
            "--state-file",
            str(state_file),
            "--output",
            str(output),
            "--session-root",
            str(session_root),
        ],
    )
    inspected = runner.invoke(
        app,
        [
            "session",
            "inspect",
            "--profile",
            "profile-cli",
            "--output",
            str(output),
            "--session-root",
            str(session_root),
        ],
    )

    assert imported.exit_code == 0, imported.output
    assert inspected.exit_code == 0, inspected.output
    assert json.loads(imported.stdout) == json.loads(inspected.stdout)
    assert "fixture-secret" not in imported.stdout
    assert "fixture-secret" not in inspected.stdout


def test_guided_login_uses_the_same_non_secret_metadata_contract(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    state = {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]}
    output = tmp_path / "operator-data"
    session_root = tmp_path / "private-sessions"
    monkeypatch.setattr("app.cli.main.collect_guided_storage_state", lambda _url: state)

    result = CliRunner().invoke(
        app,
        [
            "session",
            "login",
            "--profile",
            "profile-guided",
            "--output",
            str(output),
            "--session-root",
            str(session_root),
        ],
    )

    assert result.exit_code == 0, result.output
    metadata = json.loads(result.stdout)
    assert metadata["session_class"] == "guided_login"
    assert set(metadata) == {
        "cookie_count",
        "created_at",
        "encrypted_sha256",
        "health",
        "inspected_at",
        "origin_count",
        "profile_id",
        "session_class",
        "source_browser",
        "storage_version",
    }
