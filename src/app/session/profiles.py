"""Encrypted session envelopes and non-secret profile metadata."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from re import fullmatch
from tempfile import NamedTemporaryFile
from typing import TypedDict, cast

from app.session.dpapi import DpapiError, protect_for_current_user, unprotect_for_current_user
from app.session.health import (
    SessionHealth,
    SessionHealthResult,
    SessionProbe,
    classify_observation,
)


class SessionEnvelopeError(ValueError):
    """Raised when a supplied browser storage state is invalid."""


class StorageState(TypedDict):
    """The constrained Playwright storage-state envelope accepted in Phase 1."""

    cookies: list[object]
    origins: list[object]


@dataclass(frozen=True)
class SessionMetadata:
    """Session metadata that excludes encrypted and decrypted secret values."""

    profile_id: str
    session_class: str
    source_browser: str
    health: str
    created_at: str
    inspected_at: str
    storage_version: str
    cookie_count: int
    origin_count: int
    encrypted_sha256: str

    def as_dict(self) -> dict[str, object]:
        """Return safe JSON command output."""
        return self.__dict__.copy()


class SessionProfileService:
    """Persist Playwright session states with Windows user-bound encryption."""

    def __init__(self, connection: sqlite3.Connection, session_root: Path) -> None:
        self.connection = connection
        self.session_root = session_root.resolve()
        repository_root = Path(__file__).resolve().parents[3]
        if (repository_root / ".git").is_dir() and self.session_root.is_relative_to(
            repository_root
        ):
            raise SessionEnvelopeError("session root must be outside the repository")

    def import_state(
        self,
        profile_id: str,
        state: Mapping[str, object],
        *,
        source_browser: str = "imported_storage_state",
    ) -> SessionMetadata:
        """Validate, encrypt, and persist an imported Playwright storage state."""
        return self._save(profile_id, "imported", source_browser, state)

    def save_guided_state(
        self,
        profile_id: str,
        state: Mapping[str, object],
        *,
        source_browser: str = "playwright_chromium",
    ) -> SessionMetadata:
        """Persist a visible guided-login state with the imported-state metadata contract."""
        return self._save(profile_id, "guided_login", source_browser, state)

    def browser_profile_directory(self, profile_id: str) -> Path:
        """Return one validated, scanner-owned persistent browser profile directory."""
        self._path(profile_id)
        directory = (self.session_root / "browser-profiles" / profile_id).resolve()
        if not directory.is_relative_to(self.session_root):
            raise SessionEnvelopeError("browser profile directory is outside the session root")
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def read_state(self, profile_id: str) -> StorageState:
        """Decrypt and validate a session envelope for browser-context recreation."""
        try:
            encrypted = self._path(profile_id).read_bytes()
            metadata = json.loads(self._row(profile_id)["metadata_json"])
            if sha256(encrypted).hexdigest() != metadata.get("encrypted_sha256"):
                raise SessionEnvelopeError("session envelope hash mismatch")
            plaintext = unprotect_for_current_user(encrypted)
            state = json.loads(plaintext)
            return self._validate_state(state)
        except (DpapiError, OSError, json.JSONDecodeError, SessionEnvelopeError) as error:
            self._set_health(profile_id, "session_invalid")
            raise SessionEnvelopeError(
                f"session decryption or integrity check failed: {profile_id}"
            ) from error

    def inspect(self, profile_id: str) -> SessionMetadata:
        """Return safe metadata and validate the encrypted envelope before reporting healthy."""
        row = self._row(profile_id)
        try:
            self.read_state(profile_id)
            row = self._row(profile_id)
        except SessionEnvelopeError:
            row = self._row(profile_id)
        return self._metadata(row)

    def probe_health(
        self,
        profile_id: str,
        route: str,
        probe: SessionProbe,
    ) -> SessionHealthResult:
        """Probe one authenticated route through either stored session method."""
        try:
            observation = probe(route, self.read_state(profile_id))
            result = classify_observation(observation)
        except (SessionEnvelopeError, OSError, ValueError):
            result = SessionHealthResult(SessionHealth.INVALID, ("session_state_invalid",))
        persisted_health = {
            SessionHealth.READY: "observed",
            SessionHealth.EXPIRED: "session_expired",
            SessionHealth.CHALLENGED: "session_challenged",
            SessionHealth.RESTRICTED: "session_restricted",
            SessionHealth.INVALID: "session_invalid",
        }[result.health]
        self._set_health(profile_id, persisted_health)
        return result

    def delete(self, profile_id: str) -> None:
        """Delete one encrypted envelope and its non-secret profile metadata."""
        self._row(profile_id)
        path = self._path(profile_id)
        if path.exists():
            path.unlink()
        with self.connection:
            self.connection.execute(
                "DELETE FROM session_profiles WHERE profile_id = ?", (profile_id,)
            )

    def _save(
        self,
        profile_id: str,
        session_class: str,
        source_browser: str,
        state: Mapping[str, object],
    ) -> SessionMetadata:
        if not profile_id:
            raise SessionEnvelopeError("profile_id must be non-empty")
        normalized = self._validate_state(state)
        plaintext = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
        encrypted = protect_for_current_user(plaintext)
        self._write_envelope(profile_id, encrypted)
        now = datetime.now(UTC).isoformat()
        metadata = {
            "storage_version": "1.0",
            "cookie_count": len(normalized["cookies"]),
            "origin_count": len(normalized["origins"]),
            "encrypted_sha256": sha256(encrypted).hexdigest(),
        }
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO session_profiles(
                    profile_id, session_class, source_browser, health, created_at,
                    inspected_at, metadata_json
                ) VALUES (?, ?, ?, 'observed', ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    session_class = excluded.session_class,
                    source_browser = excluded.source_browser,
                    health = excluded.health,
                    inspected_at = excluded.inspected_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    profile_id,
                    session_class,
                    source_browser,
                    now,
                    now,
                    json.dumps(metadata, sort_keys=True),
                ),
            )
        return self.inspect(profile_id)

    def _write_envelope(self, profile_id: str, encrypted: bytes) -> None:
        path = self._path(profile_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, delete=False) as destination:
            temporary = Path(destination.name)
            destination.write(encrypted)
            destination.flush()
            os.fsync(destination.fileno())
        temporary.replace(path)

    def _path(self, profile_id: str) -> Path:
        if fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", profile_id) is None:
            raise SessionEnvelopeError(
                "profile_id must use letters, numbers, underscores, or hyphens"
            )
        path = (self.session_root / f"{profile_id}.dpapi").resolve()
        if not path.is_relative_to(self.session_root):
            raise SessionEnvelopeError("profile path is outside the session root")
        return path

    def _row(self, profile_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM session_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if row is None:
            raise SessionEnvelopeError(f"session profile not found: {profile_id}")
        return row

    def _set_health(self, profile_id: str, health: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE session_profiles SET health = ?, inspected_at = ? WHERE profile_id = ?",
                (health, datetime.now(UTC).isoformat(), profile_id),
            )

    @staticmethod
    def _metadata(row: sqlite3.Row) -> SessionMetadata:
        metadata = json.loads(row["metadata_json"])
        return SessionMetadata(
            profile_id=row["profile_id"],
            session_class=row["session_class"],
            source_browser=row["source_browser"],
            health=row["health"],
            created_at=row["created_at"],
            inspected_at=row["inspected_at"],
            storage_version=metadata["storage_version"],
            cookie_count=metadata["cookie_count"],
            origin_count=metadata["origin_count"],
            encrypted_sha256=metadata["encrypted_sha256"],
        )

    @staticmethod
    def _validate_state(value: object) -> StorageState:
        if not isinstance(value, Mapping) or set(value) != {"cookies", "origins"}:
            raise SessionEnvelopeError("storage state must contain only cookies and origins")
        data = dict(value)
        cookies, origins = data.get("cookies"), data.get("origins")
        if not isinstance(cookies, list) or not isinstance(origins, list):
            raise SessionEnvelopeError("storage state cookies and origins must be arrays")
        return {"cookies": cast(list[object], cookies), "origins": cast(list[object], origins)}
