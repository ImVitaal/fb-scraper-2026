"""Tests for synthetic discovery through the active-session contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.discovery import SessionDiscoveryFixtureAdapter


def test_fixture_discovery_requires_session_state_before_reading_capture(tmp_path: Path) -> None:
    fixture = tmp_path / "discovery.html"
    fixture.write_bytes(b"<section data-pgscan-discovery='1'></section>")

    with pytest.raises(ValueError, match="active session"):
        SessionDiscoveryFixtureAdapter({"cookies": [], "origins": []}).capture(fixture)


def test_fixture_discovery_returns_bytes_for_an_active_session(tmp_path: Path) -> None:
    fixture = tmp_path / "discovery.html"
    expected = b"<section data-pgscan-discovery='1'></section>"
    fixture.write_bytes(expected)
    state = {
        "cookies": [{"name": "fixture", "value": "secret"}],
        "origins": [],
    }

    assert SessionDiscoveryFixtureAdapter(state).capture(fixture) == expected
