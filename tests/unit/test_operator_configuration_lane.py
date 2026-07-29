"""Tests for repeatable connected operator-workflow configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.configuration import ConfigurationError, OperatorRunConfiguration


def test_operator_configuration_loads_imported_discovery_workflow(tmp_path: Path) -> None:
    path = tmp_path / "operator.toml"
    path.write_text(
        """
        [run]
        mode = "operator"
        output = "operator-data"
        raw_root = "../private-raw"
        session_root = "../private-sessions"

        [session]
        method = "imported"
        profile = "fixture-import"
        state_file = "private/state.json"

        [target]
        method = "discovery"
        fixture = "fixtures/discovery.html"
        keyword = "garden"
        location = "Bristol"
        select = "garden-top"
        """,
        encoding="utf-8",
    )

    configuration = OperatorRunConfiguration.load(path)

    assert configuration.output == tmp_path / "operator-data"
    assert configuration.raw_root == tmp_path.parent / "private-raw"
    assert configuration.session_root == tmp_path.parent / "private-sessions"
    assert configuration.session.method == "imported"
    assert configuration.session.state_file == tmp_path / "private" / "state.json"
    assert configuration.target.method == "discovery"
    assert configuration.target.fixture == tmp_path / "fixtures" / "discovery.html"
    assert configuration.target.select == "garden-top"


@pytest.mark.parametrize(
    "content",
    [
        """
        [run]
        mode = "operator"
        output = "o"
        raw_root = "r"
        session_root = "s"
        [session]
        method = "imported"
        profile = "p"
        [target]
        method = "url"
        url = "https://example.test/groups/one"
        """,
        """
        [run]
        mode = "operator"
        output = "o"
        raw_root = "r"
        session_root = "s"
        [session]
        method = "existing"
        profile = "p"
        [target]
        method = "discovery"
        fixture = "discovery.html"
        keyword = "garden"
        location = "Bristol"
        """,
        """
        [run]
        mode = "operator"
        output = "o"
        raw_root = "r"
        session_root = "s"
        unexpected = true
        [session]
        method = "guided"
        profile = "p"
        [target]
        method = "url"
        url = "https://example.test/groups/one"
        """,
    ],
)
def test_operator_configuration_rejects_incomplete_or_ambiguous_workflows(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "operator.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationError):
        OperatorRunConfiguration.load(path)
