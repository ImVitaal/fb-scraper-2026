"""Phase 4F immediate-stop receipts and secret-redaction evidence."""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from app.capture import BrowserCaptureLimits, BrowserStateError, PlaywrightGroupCaptureAdapter
from app.cli.main import _capture_selected
from app.configuration import OperatorProtectionConfiguration
from app.session import SessionProfileService
from app.storage.database import Database
from app.targets import TargetPreparationService
from app.workflows.operator_receipt import OperatorRunReceiptWriter

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


def test_partial_stop_receipt_hashes_durable_identifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, initial_receipt = _protected_stop(tmp_path, monkeypatch, "challenge")
    run_id = str(initial_receipt["run_id"])
    output = tmp_path / "output"
    observed_at = datetime.now().astimezone().isoformat()
    capture_id = "partial-stop-capture"

    with Database(output / "scanner.sqlite3") as database:
        database.connection.execute(
            """
            INSERT INTO raw_captures(
                capture_id, sha256, source_url, collected_at, storage_path, byte_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (capture_id, "a" * 64, "https://example.test/group", observed_at, "partial", 7),
        )
        database.connection.execute(
            """
            INSERT INTO groups(
                group_id, canonical_url, observed_at, raw_capture_id, schema_version, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "9100001",
                "https://example.test/groups/9100001",
                observed_at,
                capture_id,
                "1.0",
                "{}",
            ),
        )
        database.connection.execute(
            """
            INSERT INTO posts(
                post_id, group_id, canonical_url, observed_at, raw_capture_id,
                schema_version, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "9200001",
                "9100001",
                "https://example.test/groups/9100001/posts/9200001",
                observed_at,
                capture_id,
                "1.0",
                '{"comments_count": 1}',
            ),
        )
        database.connection.execute(
            """
            INSERT INTO comments(
                comment_id, post_id, group_id, parent_comment_id, observed_at,
                raw_capture_id, schema_version, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "9300001",
                "9200001",
                "9100001",
                None,
                observed_at,
                capture_id,
                "1.0",
                "{}",
            ),
        )
        database.connection.commit()

    rewritten = OperatorRunReceiptWriter(output).write_stop(
        run_id,
        BrowserCaptureLimits(),
        protection=cast(dict[str, object], initial_receipt["protection"]),
        stop_reason="challenge",
    )
    receipt = json.loads(rewritten.path.read_text(encoding="utf-8"))
    identifiers = ["comment:9300001", "group:9100001", "post:9200001"]
    expected = sha256(
        json.dumps(
            identifiers,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    assert receipt["counts"] == {"comments": 1, "failures": 1, "groups": 1, "posts": 1}
    assert receipt["identifier_set_sha256"] == expected
