"""Redacted receipt contract for a keyword-driven membership transition."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from app.capture import BrowserCaptureLimits
from app.session import SessionProfileService
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets import TargetPreparationService
from app.workflows.operator_receipt import OperatorRunReceiptWriter


def test_stop_receipt_links_a_redacted_keyword_join_transition(tmp_path: Path) -> None:
    """A stopped capture retains auditable membership evidence without private values."""
    output = tmp_path / "output"
    session_root = tmp_path / "sessions"
    run_id = "join-receipt-run"
    canonical_url = "https://app.invalid/groups/garden-bristol"
    discovery_capture = "discovery-capture"
    discovery_sha256 = "d" * 64
    confirmation_capture = "confirmation-capture"
    confirmation_sha256 = "c" * 64
    profile = "operator-profile"
    telemetry = {
        "action": "join_requested",
        "action_attempts": 1,
        "candidate_url_sha256": sha256(canonical_url.encode("utf-8")).hexdigest(),
        "confirmation_raw_sha256": confirmation_sha256,
        "discovery_query_sha256": sha256(b"garden\x00Bristol").hexdigest(),
        "discovery_raw_sha256": discovery_sha256,
        "membership_after": "joined",
        "membership_before": "join_available",
        "pacing_delay_seconds": 10.0,
        "retry_count": 0,
        "retry_waits_seconds": [],
        "transition_state": "joined",
    }

    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        SessionProfileService(database.connection, session_root).import_state(
            profile, {"cookies": [], "origins": []}
        )
        targets = TargetPreparationService(database.connection)
        selected = targets.add_url(canonical_url)
        candidate = database.connection.execute(
            "SELECT candidate_hit_id FROM selected_targets WHERE campaign_id = ?",
            (selected.campaign_id,),
        ).fetchone()
        assert candidate is not None
        now = datetime.now(UTC).isoformat()
        for capture_id, capture_sha256 in (
            (discovery_capture, discovery_sha256),
            (confirmation_capture, confirmation_sha256),
        ):
            database.connection.execute(
                """
                INSERT INTO raw_captures(
                    capture_id, sha256, source_url, collected_at, storage_path, byte_count
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    capture_id,
                    capture_sha256,
                    canonical_url,
                    now,
                    f"{capture_id}.html.gz",
                    7,
                ),
            )
        database.connection.execute(
            "UPDATE candidate_hits SET raw_capture_id = ? WHERE hit_id = ?",
            (discovery_capture, candidate["candidate_hit_id"]),
        )
        database.connection.execute(
            """
            INSERT INTO membership_transitions(
                transition_id, campaign_id, candidate_hit_id, group_id, action, state,
                planned_at, actioned_at, completed_at, confirmation_capture_id, telemetry_json
            ) VALUES (?, ?, ?, ?, 'join', 'joined', ?, ?, ?, ?, ?)
            """,
            (
                "transition-1",
                selected.campaign_id,
                candidate["candidate_hit_id"],
                selected.group_id,
                now,
                now,
                now,
                confirmation_capture,
                json.dumps(telemetry, sort_keys=True, separators=(",", ":")),
            ),
        )
        JobRepository(database.connection).create(run_id)
        LiveRunRepository(database.connection).create(
            run_id,
            profile,
            selected,
            datetime.now(UTC) - timedelta(days=30),
            "app_rendered_html/1.0",
        )
        database.connection.commit()

    receipt = OperatorRunReceiptWriter(output).write_stop(
        run_id,
        BrowserCaptureLimits(),
        protection={"stop_reason": "challenge"},
        stop_reason="challenge",
    )
    payload = json.loads(receipt.path.read_text(encoding="utf-8"))

    transition = payload["membership_transition"]
    assert transition == telemetry
    assert (
        payload["membership_transition_sha256"]
        == sha256(
            json.dumps(telemetry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    assert payload["schema_version"] == "1.2"
    redacted = receipt.path.read_text(encoding="utf-8")
    assert canonical_url not in redacted
    assert profile not in redacted


def test_discovery_stop_receipt_keeps_the_redacted_membership_transition(tmp_path: Path) -> None:
    """A warning or pending result before selection still has one auditable receipt."""
    output = tmp_path / "output"
    transition = {
        "action": "join_requested",
        "action_attempts": 1,
        "candidate_url_sha256": "a" * 64,
        "discovery_query_sha256": "b" * 64,
        "discovery_raw_sha256": "c" * 64,
        "membership_before": "join_available",
        "retry_count": 0,
        "retry_waits_seconds": [],
        "stop_reason": "challenge",
    }

    receipt = OperatorRunReceiptWriter(output).write_discovery_stop(
        "discovery-stop-receipt",
        profile="operator-profile",
        protection={"membership_transition": transition},
        stop_reason="challenge",
    )
    payload = json.loads(receipt.path.read_text(encoding="utf-8"))

    assert payload["membership_transition"] == transition
    assert (
        payload["membership_transition_sha256"]
        == sha256(
            json.dumps(
                transition, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
    )
    assert payload["schema_version"] == "1.2"
    assert "operator-profile" not in receipt.path.read_text(encoding="utf-8")
