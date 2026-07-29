"""Connected operator-workflow tests for imported and guided TOML runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from app.cli.main import app
from app.session import SessionProfileService
from app.storage.database import Database


def _write_discovery(path: Path) -> None:
    path.write_text(
        """
        <section data-pgscan-discovery="1" data-keyword="garden" data-location="Bristol">
          <article data-pgscan-candidate="1" data-group-id="garden-top"
            data-canonical-url="https://example.test/groups/garden-top"
            data-name="Bristol Gardeners" data-keyword-score="1"
            data-location-score="1"></article>
        </section>
        """,
        encoding="utf-8",
    )


def _write_configuration(
    path: Path,
    *,
    session_method: str,
    target_block: str,
) -> None:
    session_extra = 'state_file = "state.json"' if session_method == "imported" else ""
    path.write_text(
        f"""
        [run]
        mode = "operator"
        output = "operator-data"
        raw_root = "private-raw"
        session_root = "private-sessions"

        [session]
        method = "{session_method}"
        profile = "profile-{session_method}"
        {session_extra}

        [target]
        {target_block}
        """,
        encoding="utf-8",
    )


@pytest.mark.parametrize("session_method", ["imported", "guided"])
def test_operator_toml_connects_session_discovery_selection_and_capture(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    session_method: str,
) -> None:
    state = {
        "cookies": [{"name": "session_cookie", "value": "fixture-secret"}],
        "origins": [],
    }
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_discovery(tmp_path / "discovery.html")
    config = tmp_path / "operator.toml"
    _write_configuration(
        config,
        session_method=session_method,
        target_block="""
        method = "discovery"
        fixture = "discovery.html"
        keyword = "garden"
        location = "Bristol"
        select = "garden-top"
        """,
    )
    monkeypatch.setattr("app.cli.main.collect_guided_storage_state", lambda _url: state)
    captured: dict[str, str] = {}

    def fake_capture(profile: str, campaign: str, **_: object) -> dict[str, object]:
        captured.update(profile=profile, campaign=campaign)
        return {"identifiers": ["group:garden-top"], "job_id": "fixture-job", "state": "completed"}

    monkeypatch.setattr("app.cli.main._capture_selected", fake_capture)

    result = CliRunner().invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {
        "identifiers": ["group:garden-top"],
        "job_id": "fixture-job",
        "state": "completed",
    }
    assert captured["profile"] == f"profile-{session_method}"
    assert captured["campaign"]
    assert "fixture-secret" not in result.stdout
    assert "state.json" not in result.stdout
    assert "private-sessions" not in result.stdout
    with Database(tmp_path / "operator-data" / "scanner.sqlite3") as database:
        metadata = SessionProfileService(
            database.connection, tmp_path / "private-sessions"
        ).inspect(f"profile-{session_method}")
    assert set(metadata.as_dict()) == {
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


@pytest.mark.parametrize(
    ("target_block", "group_id"),
    [
        (
            'method = "url"\nurl = "https://example.test/groups/direct-one?ref=fixture"',
            "direct-one",
        ),
        ('method = "csv"\ncsv_file = "groups.csv"\nselect = "csv-two"', "csv-two"),
    ],
)
def test_operator_toml_supports_direct_url_and_csv_fallbacks(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    target_block: str,
    group_id: str,
) -> None:
    state = {"cookies": [{"name": "fixture", "value": "secret"}], "origins": []}
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (tmp_path / "groups.csv").write_text(
        "group_url,name\n"
        "https://example.test/groups/csv-one,One\n"
        "https://example.test/groups/csv-two,Two\n",
        encoding="utf-8",
    )
    config = tmp_path / "operator.toml"
    _write_configuration(config, session_method="imported", target_block=target_block)
    observed: dict[str, str] = {}

    def fake_capture(profile: str, campaign: str, **_: object) -> dict[str, object]:
        observed.update(profile=profile, campaign=campaign)
        return {"identifiers": [f"group:{group_id}"], "job_id": "fixture-job", "state": "completed"}

    monkeypatch.setattr("app.cli.main._capture_selected", fake_capture)

    result = CliRunner().invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["identifiers"] == [f"group:{group_id}"]
    assert observed["profile"] == "profile-imported"
    assert observed["campaign"]


def test_guided_run_prompts_for_one_connected_operator_workflow(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    state = {"cookies": [{"name": "fixture", "value": "secret"}], "origins": []}
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    observed: dict[str, str] = {}

    def fake_capture(profile: str, campaign: str, **_: object) -> dict[str, object]:
        observed.update(profile=profile, campaign=campaign)
        return {"identifiers": ["group:guided-one"], "job_id": "fixture-job", "state": "completed"}

    monkeypatch.setattr("app.cli.main._capture_selected", fake_capture)
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--guided",
            "--output",
            str(tmp_path / "operator-data"),
            "--raw-root",
            str(tmp_path / "private-raw"),
            "--session-root",
            str(tmp_path / "private-sessions"),
        ],
        input=(
            f"imported\nguided-profile\n{state_file}\nurl\nhttps://example.test/groups/guided-one\n"
        ),
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout.splitlines()[-1])["identifiers"] == ["group:guided-one"]
    assert observed["profile"] == "guided-profile"
    assert str(state_file) not in result.stdout
