"""Phase 4F immediate-stop receipts and secret-redaction evidence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.capture import BrowserStateError, PlaywrightGroupCaptureAdapter
from app.cli.main import _capture_selected
from app.configuration import OperatorProtectionConfiguration
from app.session import SessionProfileService
from app.storage.database import Database
from app.targets import TargetPreparationService

FAILURE = Path(__file__).parents[1] / "fixtures" / "phase4b_browser" / "failure.html"


def _protected_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> tuple[str, dict[str, object]]:
    output = tmp_path / "output"
    raw_root = tmp_path / "raw"
    session_root = tmp_path / "sessions"
    cookie_value = "SESSION_VALUE_SENTINEL_4F"
    storage_value = "STORAGE_VALUE_SENTINEL_4F"
    storage_state = {
        "cookies": [
            {
                "name": "fixture_cookie",
                "value": cookie_value,
                "domain": "example.test",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ],
        "origins": [
            {
                "origin": "https://example.test",
                "localStorage": [{"name": "fixture_token", "value": storage_value}],
            }
        ],
    }
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            "secret-profile",
            storage_state,
        )
        selected = TargetPreparationService(database.connection).add_url(
            "https://app.invalid/groups/9100001"
        )

    class _WarningAdapter(PlaywrightGroupCaptureAdapter):
        def capture_pages(
            self,
            target_url: str,
            *,
            lower_bound: datetime | None = None,
        ):
            return super().capture_pages(
                f"{FAILURE.resolve().as_uri()}?state={state}",
                lower_bound=lower_bound,
            )

    monkeypatch.setattr("app.cli.main.PlaywrightGroupCaptureAdapter", _WarningAdapter)
    protection = OperatorProtectionConfiguration(
        navigation_delay_seconds=(0.0, 0.0),
        scroll_delay_seconds=(0.0, 0.0),
        expansion_delay_seconds=(0.0, 0.0),
        retry_delays_seconds=(0.0, 0.0),
    )

    with pytest.raises(BrowserStateError):
        _capture_selected(
            "secret-profile",
            selected.campaign_id,
            output=output,
            raw_root=raw_root,
            session_root=session_root,
            headless=True,
            protection=protection,
        )

    receipt_path = next((output / "exports").glob("*.operator-receipt.json"))
    text = receipt_path.read_text(encoding="utf-8")
    return text, json.loads(text)


@pytest.mark.parametrize(
    ("state", "expected"), [("challenge", "challenge"), ("restricted", "restricted")]
)
def test_challenge_and_restriction_stop_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    expected: str,
) -> None:
    text, receipt = _protected_stop(tmp_path, monkeypatch, state)

    protection = receipt["protection"]
    assert isinstance(protection, dict)
    protection = cast(dict[str, Any], protection)
    assert protection["stop_reason"] == expected
    assert protection["retry_count"] == 0
    assert protection["retry_waits_seconds"] == []
    assert "SESSION_VALUE_SENTINEL_4F" not in text
    assert "STORAGE_VALUE_SENTINEL_4F" not in text
    assert "fixture_cookie" not in text
    assert "fixture_token" not in text
