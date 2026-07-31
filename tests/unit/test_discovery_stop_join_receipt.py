"""Join-stop discovery receipt stays redacted and integrity-addressable."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from app.workflows.operator_receipt import OperatorRunReceiptWriter


def test_discovery_stop_receipt_promotes_redacted_join_transition(tmp_path: Path) -> None:
    transition = {
        "action": "join_requested",
        "candidate_url_sha256": "a" * 64,
        "stop_reason": "challenge",
    }
    receipt = OperatorRunReceiptWriter(tmp_path).write_discovery_stop(
        "receipt-1",
        profile="profile-sensitive",
        protection={"membership_transition": transition},
        stop_reason="challenge",
    )
    payload = json.loads(receipt.path.read_text(encoding="utf-8"))

    assert payload["membership_transition"] == transition
    assert (
        payload["membership_transition_sha256"]
        == sha256(
            json.dumps(transition, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    assert payload["schema_version"] == "1.2"
    assert "profile-sensitive" not in receipt.path.read_text(encoding="utf-8")
