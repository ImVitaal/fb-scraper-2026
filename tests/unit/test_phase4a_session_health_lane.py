"""Phase 4A authenticated session-health behavior tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from app.session.health import ProbeObservation, SessionHealth, classify_observation
from app.session.profiles import SessionProfileService
from app.storage.database import Database


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (ProbeObservation(200, "/home", "authenticated-shell"), SessionHealth.READY),
        (ProbeObservation(401, "/login", "login required"), SessionHealth.EXPIRED),
        (ProbeObservation(200, "/checkpoint", "security check"), SessionHealth.CHALLENGED),
        (ProbeObservation(403, "/home", "access restricted"), SessionHealth.RESTRICTED),
        (ProbeObservation(None, "", "", navigation_error=True), SessionHealth.INVALID),
    ],
)
def test_session_failure_classification_is_explicit(
    observation: ProbeObservation,
    expected: SessionHealth,
) -> None:
    assert classify_observation(observation).health is expected


def test_imported_and_guided_profiles_use_one_probe_and_emit_no_secrets(
    tmp_path: Path,
) -> None:
    state = {
        "cookies": [{"name": "cookie-name", "value": "cookie-secret"}],
        "origins": [{"origin": "https://app.test", "localStorage": []}],
    }
    observations = iter(
        [
            ProbeObservation(200, "/home", "authenticated-shell"),
            ProbeObservation(200, "/home", "authenticated-shell"),
        ]
    )
    calls: list[dict[str, object]] = []

    def probe(route: str, storage_state: Mapping[str, object]) -> ProbeObservation:
        calls.append({"route": route, "state": storage_state})
        return next(observations)

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        service = SessionProfileService(database.connection, tmp_path / "sessions")
        imported = service.import_state("imported", state)
        guided = service.save_guided_state("guided", state)

        imported_health = service.probe_health("imported", "https://app.test/me", probe)
        guided_health = service.probe_health("guided", "https://app.test/me", probe)

        assert imported.health == guided.health == "observed"
        assert imported_health.health is SessionHealth.READY
        assert guided_health.health is SessionHealth.READY
        assert service.inspect("imported").health == "observed"
        assert service.inspect("guided").health == "observed"

    output = json.dumps(
        [imported_health.as_dict(), guided_health.as_dict()],
        sort_keys=True,
    )
    assert "cookie-secret" not in output
    assert "cookie-name" not in output
    assert "app.test" not in output
    assert len(calls) == 2
    assert calls[0]["state"] == calls[1]["state"]


def test_classifier_does_not_return_probe_text_or_route() -> None:
    observation = ProbeObservation(
        200,
        "/checkpoint?token=fixture-secret",
        "security check fixture-secret",
    )

    result = classify_observation(observation)

    assert result == replace(result, evidence=result.evidence)
    assert "fixture-secret" not in json.dumps(result.as_dict())
