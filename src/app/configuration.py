"""Repeatable, non-secret TOML configuration for fixture workflow execution."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


class ConfigurationError(ValueError):
    """Raised when a repeatable operator configuration is malformed."""


@dataclass(frozen=True)
class FixtureRunConfiguration:
    """The file locations required by one raw-to-replay fixture run."""

    fixture: Path
    output: Path
    raw_root: Path

    @classmethod
    def load(cls, path: Path) -> FixtureRunConfiguration:
        """Load a minimal `[run]` TOML configuration relative to its file."""
        try:
            with path.open("rb") as source:
                payload = tomllib.load(source)
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ConfigurationError(f"invalid configuration: {path}") from error
        if set(payload) != {"run"} or not isinstance(payload["run"], dict):
            raise ConfigurationError("configuration must contain only a [run] table")
        values = payload["run"]
        if set(values) != {"fixture", "output", "raw_root"}:
            raise ConfigurationError("[run] must contain fixture, output, and raw_root")
        return cls(
            fixture=cls._path(values, "fixture", path.parent),
            output=cls._path(values, "output", path.parent),
            raw_root=cls._path(values, "raw_root", path.parent),
        )

    @staticmethod
    def _path(values: dict[str, Any], name: str, parent: Path) -> Path:
        value = values.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"[run].{name} must be a non-empty string")
        path = Path(value)
        return path if path.is_absolute() else (parent / path).resolve()


SessionMethod = Literal["existing", "imported", "guided"]
TargetMethod = Literal["discovery", "live_discovery", "url", "csv"]


@dataclass(frozen=True)
class OperatorSessionConfiguration:
    """One existing, imported, or guided encrypted-session preparation."""

    method: SessionMethod
    profile: str
    state_file: Path | None = None
    start_url: str = "https://www.facebook.com/"


@dataclass(frozen=True)
class OperatorTargetConfiguration:
    """One session-aware discovery or fallback target preparation."""

    method: TargetMethod
    select: str | None = None
    fixture: Path | None = None
    keyword: str | None = None
    location: str | None = None
    base_url: str | None = None
    url: str | None = None
    csv_file: Path | None = None


@dataclass(frozen=True)
class OperatorRunConfiguration:
    """Repeatable connected session, target-selection, and capture workflow."""

    output: Path
    raw_root: Path
    session_root: Path
    session: OperatorSessionConfiguration
    target: OperatorTargetConfiguration
    headless: bool = False

    @classmethod
    def load(cls, path: Path) -> OperatorRunConfiguration:
        """Load one strict operator workflow configuration."""
        payload = _load_toml(path)
        if set(payload) != {"run", "session", "target"}:
            raise ConfigurationError(
                "operator configuration must contain [run], [session], and [target]"
            )
        run = _table(payload, "run")
        required_run = {"mode", "output", "raw_root", "session_root"}
        if not required_run.issubset(run) or set(run) - (required_run | {"headless"}):
            raise ConfigurationError(
                "[run] must contain mode, output, raw_root, and session_root; headless is optional"
            )
        if run.get("mode") != "operator":
            raise ConfigurationError("[run].mode must be 'operator'")
        headless = run.get("headless", False)
        if not isinstance(headless, bool):
            raise ConfigurationError("[run].headless must be true or false")
        return cls(
            output=_path(run, "output", path.parent, "run"),
            raw_root=_path(run, "raw_root", path.parent, "run"),
            session_root=_path(run, "session_root", path.parent, "run"),
            session=cls._session(_table(payload, "session"), path.parent),
            target=cls._target(_table(payload, "target"), path.parent),
            headless=headless,
        )

    @staticmethod
    def is_operator(path: Path) -> bool:
        """Identify an operator configuration without weakening strict loading."""
        payload = _load_toml(path)
        run = payload.get("run")
        return isinstance(run, dict) and run.get("mode") == "operator"

    @staticmethod
    def _session(values: dict[str, Any], parent: Path) -> OperatorSessionConfiguration:
        method = values.get("method")
        if method not in {"existing", "imported", "guided"}:
            raise ConfigurationError("[session].method must be existing, imported, or guided")
        profile = _text(values, "profile", "session")
        expected = {
            "existing": {"method", "profile"},
            "imported": {"method", "profile", "state_file"},
            "guided": {"method", "profile"},
        }[method]
        allowed = expected | ({"start_url"} if method == "guided" else set())
        if set(values) - allowed or not expected.issubset(values):
            raise ConfigurationError(f"[session] has invalid fields for {method}")
        return OperatorSessionConfiguration(
            method=method,
            profile=profile,
            state_file=(
                _path(values, "state_file", parent, "session") if method == "imported" else None
            ),
            start_url=_optional_text(values, "start_url") or "https://www.facebook.com/",
        )

    @staticmethod
    def _target(values: dict[str, Any], parent: Path) -> OperatorTargetConfiguration:
        method = values.get("method")
        expected = {
            "discovery": {"method", "fixture", "keyword", "location", "select"},
            "live_discovery": {"method", "base_url", "keyword", "location", "select"},
            "url": {"method", "url"},
            "csv": {"method", "csv_file", "select"},
        }
        if method not in expected:
            raise ConfigurationError(
                "[target].method must be discovery, live_discovery, url, or csv"
            )
        if set(values) != expected[method]:
            raise ConfigurationError(f"[target] has invalid fields for {method}")
        if method == "discovery":
            return OperatorTargetConfiguration(
                method="discovery",
                select=_text(values, "select", "target"),
                fixture=_path(values, "fixture", parent, "target"),
                keyword=_text(values, "keyword", "target"),
                location=_text(values, "location", "target"),
            )
        if method == "live_discovery":
            return OperatorTargetConfiguration(
                method="live_discovery",
                select=_text(values, "select", "target"),
                base_url=_text(values, "base_url", "target").rstrip("/"),
                keyword=_text(values, "keyword", "target"),
                location=_text(values, "location", "target"),
            )
        if method == "url":
            return OperatorTargetConfiguration(
                method="url",
                url=_text(values, "url", "target"),
            )
        return OperatorTargetConfiguration(
            method="csv",
            select=_text(values, "select", "target"),
            csv_file=_path(values, "csv_file", parent, "target"),
        )


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as source:
            payload = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(f"invalid configuration: {path}") from error
    if not isinstance(payload, dict):
        raise ConfigurationError("configuration root must be a table")
    return payload


def _table(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ConfigurationError(f"[{name}] must be a table")
    return value


def _text(values: dict[str, Any], name: str, table: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"[{table}].{name} must be a non-empty string")
    return value.strip()


def _optional_text(values: dict[str, Any], name: str) -> str | None:
    if name not in values:
        return None
    return _text(values, name, "session")


def _path(values: dict[str, Any], name: str, parent: Path, table: str) -> Path:
    value = _text(values, name, table)
    path = Path(value)
    return path if path.is_absolute() else (parent / path).resolve()
