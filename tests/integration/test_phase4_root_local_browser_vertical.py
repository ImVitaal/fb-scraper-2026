"""Root-owned local-browser vertical test without replacing capture orchestration."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from app.capture import BrowserStateError, PlaywrightGroupCaptureAdapter
from app.cli.main import _capture_selected, app
from app.session import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets import TargetPreparationService
from app.workflows.live_capture import LiveCaptureWorkflow

FIXTURES = Path(__file__).parents[1] / "fixtures" / "app_operator_redacted"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path.startswith("/groups/") and "q=" in self.path:
            body = b"""
            <main role="main"><div role="list"><div role="listitem">
              <a href="https://app.invalid/groups/9100001/">REDACTED GARDEN GROUP</a>
              <span>Garden community in Bristol</span>
            </div></div></main>
            """
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


@contextmanager
def _fixture_server() -> Iterator[tuple[str, str]]:
    handler = lambda *args, **kwargs: _QuietHandler(  # noqa: E731
        *args, directory=str(FIXTURES), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        yield base, f"{base}/group_page.html"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_local_real_browser_runs_capture_and_offline_replay_without_patching_capture(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "local-browser",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/9100001"
        )

    with _fixture_server() as (_, local_url):

        class LocalBrowserAdapter(PlaywrightGroupCaptureAdapter):
            def capture_pages(
                self,
                target_url: str,
                *,
                lower_bound: datetime | None = None,
            ):
                return super().capture_pages(local_url, lower_bound=lower_bound)

        monkeypatch.setattr("app.cli.main.PlaywrightGroupCaptureAdapter", LocalBrowserAdapter)
        captured = _capture_selected(
            "local-browser",
            selected.campaign_id,
            output=output,
            raw_root=raw_root,
            session_root=session_root,
            headless=True,
        )

    assert captured["state"] == "succeeded"
    assert captured["identifiers"] == [
        "comment:9300001",
        "group:9100001",
        "post:9200001",
    ]
    run_id = str(captured["job_id"])
    receipt_path = Path(str(captured["receipt"]))
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    assert captured["receipt_sha256"] == sha256(receipt_bytes).hexdigest()
    assert receipt["normalized_sha256"] == captured["normalized_sha256"]
    assert captured["raw_sha256"] == receipt["raw_set_sha256"]
    assert receipt["session_class"] == "imported"
    assert receipt["state"] == "succeeded"
    assert receipt["counts"] == {
        "comments": 1,
        "failures": 0,
        "groups": 1,
        "posts": 1,
    }
    assert receipt["comment_reconciliation"] == {
        "matched": True,
        "visible_top_level_comments_expected": 1,
        "visible_top_level_comments_exported": 1,
    }
    assert receipt["metrics"]["run"] is not None
    assert receipt["metrics"]["replay"] is not None
    assert receipt["metrics"]["resume"] is None
    assert receipt["protection"] == {
        "delays_seconds": {
            "expansion": 0.0,
            "navigation": 0.0,
            "scroll": 0.0,
        },
        "known_posts_skipped": 0,
        "retry_count": 0,
        "retry_waits_seconds": [],
        "stop_reason": None,
    }
    assert "app.invalid" not in receipt_path.read_text(encoding="utf-8")
    assert "local-browser" not in receipt_path.read_text(encoding="utf-8")
    assert "cookies" not in receipt_path.read_text(encoding="utf-8")
    assert "origins" not in receipt_path.read_text(encoding="utf-8")
    assert {
        path.name for path in (output / "exports").iterdir() if path.name.startswith(run_id)
    } >= {
        f"{run_id}.csv",
        f"{run_id}.json",
        f"{run_id}.manifest.json",
        f"{run_id}.md",
        f"{run_id}.sqlite3",
    }
    assert len(list(raw_root.glob("*.html.gz"))) == 1
    with Database(output / "scanner.sqlite3") as database:
        row = database.connection.execute(
            "SELECT payload_json FROM groups WHERE group_id = '9100001'"
        ).fetchone()
    assert row is not None
    assert json.loads(row["payload_json"])["session_class"] == "imported"

    inspected = CliRunner().invoke(
        app,
        ["inspect", run_id, "--output", str(output)],
    )
    assert inspected.exit_code == 0, inspected.output
    inspection = json.loads(inspected.stdout)
    assert inspection["counts"] == {"comments": 1, "groups": 1, "posts": 1}
    assert inspection["pages"] == 1
    assert inspection["interactions"] == 1
    assert inspection["session_health"] == "observed"
    assert inspection["failure_class"] is None

    replay = CliRunner().invoke(
        app,
        [
            "replay",
            run_id,
            "--offline",
            "--output",
            str(output),
            "--raw-root",
            str(raw_root),
        ],
    )

    assert replay.exit_code == 0, replay.output
    replayed = json.loads(replay.stdout)
    assert replayed["identifiers"] == captured["identifiers"]


@pytest.mark.parametrize("session_method", ["imported", "guided"])
def test_operator_config_uses_real_browser_live_discovery_and_group_capture(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    session_method: str,
) -> None:
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    state_file = tmp_path / "state.json"
    state_file.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

    with _fixture_server() as (base_url, group_url):
        config = tmp_path / "operator.toml"
        session_extra = (
            f'state_file = "{state_file.as_posix()}"' if session_method == "imported" else ""
        )
        config.write_text(
            f"""
            [run]
            mode = "operator"
            headless = true
            output = "{output.as_posix()}"
            raw_root = "{raw_root.as_posix()}"
            session_root = "{session_root.as_posix()}"

            [session]
            method = "{session_method}"
            profile = "local-live"
            {session_extra}

            [target]
            method = "live_discovery"
            base_url = "{base_url}"
            keyword = "garden"
            location = "Bristol"
            select = "9100001"
            """,
            encoding="utf-8",
        )

        class LocalBrowserAdapter(PlaywrightGroupCaptureAdapter):
            def capture_pages(
                self,
                target_url: str,
                *,
                lower_bound: datetime | None = None,
            ):
                return super().capture_pages(group_url, lower_bound=lower_bound)

        from app.session.health import ProbeObservation

        monkeypatch.setattr("app.cli.main.PlaywrightGroupCaptureAdapter", LocalBrowserAdapter)
        monkeypatch.setattr(
            "app.cli.main.collect_guided_storage_state",
            lambda route: {"cookies": [], "origins": []},
        )
        monkeypatch.setattr(
            "app.cli.main.probe_with_playwright",
            lambda route, state: ProbeObservation(200, "/home", "authenticated"),
        )
        result = CliRunner().invoke(app, ["run", "--config", str(config)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["identifiers"] == [
        "comment:9300001",
        "group:9100001",
        "post:9200001",
    ]
    receipt = json.loads(Path(payload["receipt"]).read_text(encoding="utf-8"))
    protection = receipt["protection"]
    assert 10 <= protection["delays_seconds"]["navigation"] <= 20
    assert 6 <= protection["delays_seconds"]["scroll"] <= 12
    assert 3 <= protection["delays_seconds"]["expansion"] <= 7
    assert protection["between_groups_seconds"] == 900
    assert protection["workers"] == 1
    assert protection["active_groups"] == 1
    assert protection["first_group_post_limit"] == 30
    assert protection["retry_count"] == 0
    assert protection["stop_reason"] is None
    assert len(list(raw_root.glob("*.discovery.html.gz"))) == 1
    assert len([path for path in raw_root.glob("*.html.gz") if ".discovery." not in path.name]) == 1


def test_real_browser_interruption_resumes_from_durable_checkpoint(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    job_id = "local-browser-resume"
    lower_bound = datetime(2026, 7, 1, tzinfo=UTC)
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "resume-profile",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/9100001"
        )
        JobRepository(database.connection).create(job_id)
        LiveRunRepository(database.connection).create(
            job_id,
            "resume-profile",
            selected,
            lower_bound,
            "app_rendered_html/1.0",
        )

    with _fixture_server() as (_, local_url):
        interrupted_adapter = PlaywrightGroupCaptureAdapter({"cookies": [], "origins": []})
        with (
            pytest.raises(KeyboardInterrupt),
            interrupted_adapter.capture_pages(
                local_url,
                lower_bound=lower_bound,
            ) as capture,
        ):
            LiveCaptureWorkflow(output, raw_root).capture_pages(
                job_id,
                capture,
                max_pages=interrupted_adapter.limits.max_pages,
                interrupt_after_pages=1,
            )

        class LocalBrowserAdapter(PlaywrightGroupCaptureAdapter):
            def capture_pages(
                self,
                target_url: str,
                *,
                lower_bound: datetime | None = None,
            ):
                return super().capture_pages(local_url, lower_bound=lower_bound)

        monkeypatch.setattr("app.cli.main.PlaywrightGroupCaptureAdapter", LocalBrowserAdapter)
        resumed = CliRunner().invoke(
            app,
            [
                "resume",
                job_id,
                "--headless",
                "--output",
                str(output),
                "--raw-root",
                str(raw_root),
                "--session-root",
                str(session_root),
            ],
        )

    assert interrupted_adapter.closed
    assert resumed.exit_code == 0, resumed.output
    payload = json.loads(resumed.stdout)
    assert tuple(payload["identifiers"]) == (
        "comment:9300001",
        "group:9100001",
        "post:9200001",
    )
    receipt = json.loads(Path(payload["receipt"]).read_text(encoding="utf-8"))
    assert receipt["metrics"]["resume"] is not None
    assert receipt["metrics"]["replay"] is not None
    assert receipt["protection"]["between_group_wait_applied_seconds"] == 0.0
    assert len(list(raw_root.glob("*.html.gz"))) == 1
    assert len(receipt["raw_captures"]) == 1


def test_account_warning_writes_redacted_stop_receipt(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "warning-profile",
            {"cookies": [], "origins": []},
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/9100001"
        )

    failure = (
        Path(__file__).parents[1] / "fixtures" / "phase4b_browser" / "failure.html"
    ).resolve()

    class WarningBrowserAdapter(PlaywrightGroupCaptureAdapter):
        def capture_pages(
            self,
            target_url: str,
            *,
            lower_bound: datetime | None = None,
        ):
            return super().capture_pages(
                f"{failure.as_uri()}?state=login",
                lower_bound=lower_bound,
            )

    monkeypatch.setattr("app.cli.main.PlaywrightGroupCaptureAdapter", WarningBrowserAdapter)

    with pytest.raises(BrowserStateError, match="login_required"):
        _capture_selected(
            "warning-profile",
            selected.campaign_id,
            output=output,
            raw_root=raw_root,
            session_root=session_root,
            headless=True,
        )

    receipts = list((output / "exports").glob("*.operator-receipt.json"))
    assert len(receipts) == 1
    text = receipts[0].read_text(encoding="utf-8")
    receipt = json.loads(text)
    assert receipt["state"] == "failed"
    assert receipt["counts"]["failures"] == 1
    assert receipt["protection"]["stop_reason"] == "login_required"
    assert receipt["raw_captures"] == []
    assert "app.invalid" not in text
    assert "warning-profile" not in text
    assert "cookies" not in text
    assert "origins" not in text
