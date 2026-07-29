"""CLI tests for session import and safe metadata inspection."""

from __future__ import annotations

import json
from pathlib import Path

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
