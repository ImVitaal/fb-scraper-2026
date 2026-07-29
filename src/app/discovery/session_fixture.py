"""Synthetic discovery transport gated by the active-session contract."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path


class SessionDiscoveryFixtureAdapter:
    """Read one synthetic discovery capture only after session validation."""

    def __init__(self, storage_state: Mapping[str, object]) -> None:
        cookies = storage_state.get("cookies")
        origins = storage_state.get("origins")
        if not isinstance(cookies, list) or not isinstance(origins, list):
            raise ValueError("discovery requires a valid active session contract")
        self._active = bool(cookies or origins)

    def capture(self, fixture: Path) -> bytes:
        """Return fixture bytes after verifying the session is active."""
        if not self._active:
            raise ValueError("discovery requires an active session")
        return fixture.read_bytes()
