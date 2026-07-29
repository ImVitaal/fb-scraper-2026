"""Repeatable, non-secret TOML configuration for fixture workflow execution."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
