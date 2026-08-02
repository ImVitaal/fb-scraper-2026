"""Synthetic coverage for the connected Phase 4G CLI adapter."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import app.cli.main as main
from app.configuration import (
    OperatorProtectionConfiguration,
    OperatorRunConfiguration,
    OperatorSessionConfiguration,
    OperatorTargetConfiguration,
)
from app.session.health import SessionHealth, SessionHealthResult
from app.session.profiles import SessionEnvelopeError
from app.storage.database import Database
from app.targets import SelectedTarget, TargetCandidate, TargetPreparationService


def _configuration(tmp_path: Path) -> OperatorRunConfiguration:
    return OperatorRunConfiguration(
        output=tmp_path / "output",
        raw_root=tmp_path / "raw",
        session_root=tmp_path / "sessions",
        session=OperatorSessionConfiguration(method="existing", profile="profile"),
        target=OperatorTargetConfiguration(
            method="live_discovery",
            select="lowest-volume",
            keyword="garden",
            location="Bristol",
            base_url="https://www.facebook.com",
        ),
        headless=True,
        protection=OperatorProtectionConfiguration(
            navigation_delay_seconds=(0.0, 0.0),
            scroll_delay_seconds=(0.0, 0.0),
            expansion_delay_seconds=(0.0, 0.0),
            retry_delays_seconds=(0.0, 0.0),
            between_groups_seconds=0.0,
        ),
    )


class _ReadySessions:
    def __init__(self, connection, session_root: Path) -> None:
        del connection, session_root

    def read_state(self, profile: str) -> dict[str, list[object]]:
        assert profile == "profile"
        return {"cookies": [], "origins": []}

    def inspect(self, profile: str) -> SimpleNamespace:
        assert profile == "profile"
        return SimpleNamespace(source_browser="imported")

    def probe_health(self, profile: str, start_url: str, probe) -> SessionHealthResult:
        del profile, start_url, probe
        return SessionHealthResult(SessionHealth.READY, ("authenticated_route_reached",))


def _candidates() -> tuple[TargetCandidate, ...]:
    return tuple(
        TargetCandidate(
            candidate_id=f"candidate-{index}",
            group_id=f"GROUP-{index}",
            canonical_url=f"https://www.facebook.com/groups/GROUP-{index}",
            name=None,
            source="discovery",
            rank=index,
        )
        for index in range(3)
    )


def test_target_service_returns_confirmed_candidates_for_batch(tmp_path: Path) -> None:
    with Database(tmp_path / "output" / "scanner.sqlite3") as database:
        database.migrate()
        service = TargetPreparationService(database.connection)
        selected = service.add_url("https://www.facebook.com/groups/GROUP-1")
        candidates = service.get_joined_candidates(selected.campaign_id)
        assert [candidate.group_id for candidate in candidates] == ["GROUP-1"]
        with pytest.raises(ValueError, match="from one to ten"):
            service.get_joined_candidates(selected.campaign_id, limit=0)


def test_run_operator_batch_adapts_one_group_capture_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = _configuration(tmp_path)
    monkeypatch.setattr(main, "SessionProfileService", _ReadySessions)
    monkeypatch.setattr(main, "_prepare_session", lambda sessions, config: None)
    monkeypatch.setattr(
        main,
        "_prepare_target",
        lambda *args, **kwargs: SelectedTarget(
            "discovery-campaign",
            "candidate-0",
            "GROUP-0",
            "https://www.facebook.com/groups/GROUP-0",
            None,
            "discovery",
        ),
    )
    monkeypatch.setattr(
        TargetPreparationService,
        "get_joined_candidates",
        lambda self, campaign_id, limit=10: _candidates()[:limit],
    )

    def add_url(self, url: str) -> SelectedTarget:
        del self
        group_id = url.rsplit("/", 1)[-1]
        return SelectedTarget(
            f"capture-{group_id}",
            f"candidate-{group_id}",
            group_id,
            url,
            None,
            "direct_url",
        )

    monkeypatch.setattr(TargetPreparationService, "add_url", add_url)

    calls: list[str] = []

    def capture_selected(profile: str, campaign: str, **kwargs) -> dict[str, object]:
        del profile, kwargs
        calls.append(campaign)
        return {
            "identifiers": [f"group:{campaign}"],
            "job_id": f"job-{campaign}",
            "normalized_sha256": "a" * 64,
            "raw_sha256": "b" * 64,
        }

    monkeypatch.setattr(main, "_capture_selected", capture_selected)
    result = main._run_operator_batch(configuration, resume=False)

    assert result["completed_groups"] == 3
    assert result["failed_groups"] == 0
    assert calls == ["capture-GROUP-0", "capture-GROUP-1", "capture-GROUP-2"]


def test_run_operator_batch_halts_on_session_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = _configuration(tmp_path)
    monkeypatch.setattr(main, "SessionProfileService", _ReadySessions)
    monkeypatch.setattr(main, "_prepare_session", lambda sessions, config: None)
    monkeypatch.setattr(
        main,
        "_prepare_target",
        lambda *args, **kwargs: SelectedTarget(
            "discovery-campaign",
            "candidate-0",
            "GROUP-0",
            "https://www.facebook.com/groups/GROUP-0",
            None,
            "discovery",
        ),
    )
    monkeypatch.setattr(
        TargetPreparationService,
        "get_joined_candidates",
        lambda self, campaign_id, limit=10: _candidates()[:1],
    )
    monkeypatch.setattr(
        TargetPreparationService,
        "add_url",
        lambda self, url: SelectedTarget(
            "capture-campaign",
            "capture-candidate",
            url.rsplit("/", 1)[-1],
            url,
            None,
            "direct_url",
        ),
    )
    monkeypatch.setattr(
        main,
        "_capture_selected",
        lambda *args, **kwargs: (_ for _ in ()).throw(SessionEnvelopeError("profile lock")),
    )

    result = main._run_operator_batch(configuration, resume=False)
    payload = json.loads((configuration.output / "phase4g-batch.json").read_text(encoding="utf-8"))

    assert result["completed_groups"] == 0
    assert payload["state"] == "stopped"
    assert payload["groups"][0]["stop_reason"] == "local_browser_profile_lock"


def test_batch_run_accepts_operator_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "operator.toml"
    output = tmp_path / "operator-output"
    raw_root = tmp_path / "operator-raw"
    session_root = tmp_path / "operator-sessions"
    config.write_text(
        "\n".join(
            (
                "[run]",
                'mode = "operator"',
                f'output = "{output.as_posix()}"',
                f'raw_root = "{raw_root.as_posix()}"',
                f'session_root = "{session_root.as_posix()}"',
                "headless = true",
                "",
                "[session]",
                'method = "existing"',
                'profile = "profile"',
                "",
                "[target]",
                'method = "live_discovery"',
                'base_url = "https://www.facebook.com"',
                'keyword = "garden"',
                'location = "Bristol"',
            )
        ),
        encoding="utf-8",
    )
    observed: list[tuple[Path, bool]] = []

    def run_batch(configuration: OperatorRunConfiguration, *, resume: bool):
        observed.append((configuration.output, resume))
        return {"state": "completed"}

    monkeypatch.setattr(main, "_run_operator_batch", run_batch)
    result = CliRunner().invoke(main.app, ["batch-run", "--config", str(config), "--resume"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"state": "completed"}
    assert observed == [(output.resolve(), True)]
