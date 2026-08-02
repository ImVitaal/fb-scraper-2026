"""Join-stop discovery receipt stays redacted and integrity-addressable."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.capture import BrowserStateError
from app.cli import main
from app.configuration import (
    OperatorRunConfiguration,
    OperatorSessionConfiguration,
    OperatorTargetConfiguration,
)
from app.discovery import UnsupportedDiscoveryLayoutError
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


def test_operator_writes_a_redacted_receipt_when_discovery_layout_is_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configuration = OperatorRunConfiguration(
        output=tmp_path / "output",
        raw_root=tmp_path / "raw",
        session_root=tmp_path / "sessions",
        session=OperatorSessionConfiguration(method="existing", profile="profile-sensitive"),
        target=OperatorTargetConfiguration(
            method="live_join",
            base_url="https://app.invalid",
            keyword="garden",
            location="Bristol",
        ),
    )
    monkeypatch.setattr(main, "_prepare_session", lambda sessions, config: None)
    monkeypatch.setattr(main.SessionProfileService, "read_state", lambda self, profile: {})
    monkeypatch.setattr(
        main.SessionProfileService,
        "inspect",
        lambda self, profile: SimpleNamespace(source_browser="imported_storage_state"),
    )
    monkeypatch.setattr(
        main.SessionProfileService,
        "probe_health",
        lambda self, profile, route, probe: SimpleNamespace(health=SimpleNamespace(value="ready")),
    )
    monkeypatch.setattr(
        main,
        "_prepare_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            UnsupportedDiscoveryLayoutError("supported Group candidates are missing")
        ),
    )

    with pytest.raises(BrowserStateError, match="unsupported_discovery_layout"):
        main._run_operator(configuration)

    receipt_paths = list((configuration.output / "exports").glob("*.operator-receipt.json"))
    assert len(receipt_paths) == 1
    payload = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    assert payload["protection"]["stop_reason"] == "unsupported_discovery_layout"
    assert "profile-sensitive" not in receipt_paths[0].read_text(encoding="utf-8")
