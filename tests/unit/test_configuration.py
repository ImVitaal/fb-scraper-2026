"""Tests for repeatable fixture-run TOML configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.configuration import ConfigurationError, FixtureRunConfiguration


def test_load_resolves_relative_paths_from_the_configuration_file(tmp_path: Path) -> None:
    path = tmp_path / "run.toml"
    path.write_text(
        """
        [run]
        fixture = "fixtures/capture.json"
        output = "operator-data"
        raw_root = "../private-raw"
        """,
        encoding="utf-8",
    )

    configuration = FixtureRunConfiguration.load(path)

    assert configuration.fixture == tmp_path / "fixtures" / "capture.json"
    assert configuration.output == tmp_path / "operator-data"
    assert configuration.raw_root == tmp_path.parent / "private-raw"


@pytest.mark.parametrize(
    "content",
    [
        "[other]\nfixture = 'x'\n",
        "[run]\nfixture = 'x'\noutput = 'o'\n",
        "[run]\nfixture = 1\noutput = 'o'\nraw_root = 'r'\n",
    ],
)
def test_load_rejects_missing_or_non_string_required_values(tmp_path: Path, content: str) -> None:
    path = tmp_path / "run.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationError):
        FixtureRunConfiguration.load(path)
