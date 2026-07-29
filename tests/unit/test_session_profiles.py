"""Tests for Windows user-bound encrypted session profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.session.profiles import SessionEnvelopeError, SessionProfileService
from app.storage.database import Database


def test_imported_state_is_encrypted_and_has_non_secret_metadata(tmp_path: Path) -> None:
    state = {
        "cookies": [
            {"name": "session_cookie", "value": "fixture-secret", "domain": "example.test"}
        ],
        "origins": [{"origin": "https://example.test", "localStorage": []}],
    }
    database_path = tmp_path / "operator-data" / "scanner.sqlite3"
    session_root = tmp_path / "private-sessions"
    with Database(database_path) as database:
        database.migrate()
        service = SessionProfileService(database.connection, session_root)
        metadata = service.import_state("profile-imported", state)

        assert metadata.profile_id == "profile-imported"
        assert metadata.session_class == "imported"
        assert metadata.cookie_count == 1
        assert service.read_state("profile-imported") == state
        assert service.inspect("profile-imported") == metadata

    envelope = session_root / "profile-imported.dpapi"
    assert envelope.is_file()
    assert b"fixture-secret" not in envelope.read_bytes()
    assert "fixture-secret" not in json.dumps(metadata.as_dict())


def test_tampered_session_envelope_fails_closed(tmp_path: Path) -> None:
    state = {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]}
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        service = SessionProfileService(database.connection, tmp_path / "private-sessions")
        service.import_state("profile-tampered", state)
        (tmp_path / "private-sessions" / "profile-tampered.dpapi").write_bytes(b"tampered")

        assert service.inspect("profile-tampered").health == "session_invalid"


def test_profile_rejects_path_traversal_and_valid_dpapi_envelope_swaps(tmp_path: Path) -> None:
    state = {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]}
    second_state = {
        "cookies": [],
        "origins": [{"origin": "https://other.test", "localStorage": []}],
    }
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        root = tmp_path / "private-sessions"
        service = SessionProfileService(database.connection, root)
        with pytest.raises(SessionEnvelopeError):
            service.import_state("../outside", state)
        service.import_state("profile-one", state)
        service.import_state("profile-two", second_state)
        (root / "profile-one.dpapi").write_bytes((root / "profile-two.dpapi").read_bytes())

        assert service.inspect("profile-one").health == "session_invalid"
