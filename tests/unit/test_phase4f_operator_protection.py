"""Operator configuration tests for the mandatory Phase 4F protection gate."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.cli.main import _resolve_candidate
from app.configuration import ConfigurationError, OperatorRunConfiguration
from app.discovery.live import AppDiscoveryParser


def _configuration(tmp_path: Path, protection: str = "") -> Path:
    path = tmp_path / "operator.toml"
    path.write_text(
        f"""
        [run]
        mode = "operator"
        output = "output"
        raw_root = "raw"
        session_root = "sessions"

        [session]
        method = "existing"
        profile = "operator"

        [target]
        method = "live_discovery"
        base_url = "https://example.test"
        keyword = "local community"
        location = "London"
        select = "1"

        {protection}
        """,
        encoding="utf-8",
    )
    return path


def test_operator_protection_defaults_are_release_safe(tmp_path: Path) -> None:
    configuration = OperatorRunConfiguration.load(_configuration(tmp_path))

    assert configuration.protection.navigation_delay_seconds == (10.0, 20.0)
    assert configuration.protection.scroll_delay_seconds == (6.0, 12.0)
    assert configuration.protection.expansion_delay_seconds == (3.0, 7.0)
    assert configuration.protection.retry_delays_seconds == (30.0, 120.0)
    assert configuration.protection.between_groups_seconds == 900.0
    assert configuration.protection.workers == 1
    assert configuration.protection.active_groups == 1
    assert configuration.protection.first_group_post_limit == 30


def test_operator_protection_accepts_only_bounded_release_values(tmp_path: Path) -> None:
    configuration = OperatorRunConfiguration.load(
        _configuration(
            tmp_path,
            """
            [protection]
            navigation_delay_seconds = [12, 18]
            scroll_delay_seconds = [7, 11]
            expansion_delay_seconds = [4, 6]
            retry_delays_seconds = [30, 120]
            between_groups_seconds = 900
            workers = 1
            active_groups = 1
            first_group_post_limit = 20
            """,
        )
    )

    assert configuration.protection.navigation_delay_seconds == (12.0, 18.0)
    assert configuration.protection.scroll_delay_seconds == (7.0, 11.0)
    assert configuration.protection.expansion_delay_seconds == (4.0, 6.0)
    assert configuration.protection.first_group_post_limit == 20


@pytest.mark.parametrize(
    "field,value",
    [
        ("navigation_delay_seconds", "[1, 2]"),
        ("scroll_delay_seconds", "[1, 2]"),
        ("expansion_delay_seconds", "[1, 2]"),
        ("retry_delays_seconds", "[1, 2]"),
        ("between_groups_seconds", "60"),
        ("workers", "2"),
        ("active_groups", "2"),
        ("first_group_post_limit", "31"),
    ],
)
def test_operator_protection_rejects_values_below_the_gate(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    values = {
        "navigation_delay_seconds": "[10, 20]",
        "scroll_delay_seconds": "[6, 12]",
        "expansion_delay_seconds": "[3, 7]",
        "retry_delays_seconds": "[30, 120]",
        "between_groups_seconds": "900",
        "workers": "1",
        "active_groups": "1",
        "first_group_post_limit": "30",
    }
    values[field] = value
    table = "[protection]\n" + "\n".join(f"{name} = {item}" for name, item in values.items())

    with pytest.raises(ConfigurationError):
        OperatorRunConfiguration.load(_configuration(tmp_path, table))


def test_live_discovery_defaults_to_lowest_measured_volume(tmp_path: Path) -> None:
    path = _configuration(tmp_path).read_text(encoding="utf-8")
    path = path.replace('        select = "1"\n', "")
    config = tmp_path / "automatic.toml"
    config.write_text(path, encoding="utf-8")
    loaded = OperatorRunConfiguration.load(config)
    candidates = (
        SimpleNamespace(
            candidate_id="high",
            activity_posts_per_day=20,
            rank=1,
            group_id="group-high",
        ),
        SimpleNamespace(
            candidate_id="low",
            activity_posts_per_day=5,
            rank=2,
            group_id="group-low",
        ),
    )

    assert loaded.target.select == "lowest-volume"
    assert _resolve_candidate(candidates, loaded.target.select) == "low"


def test_single_joined_candidate_without_activity_is_selectable() -> None:
    candidate = SimpleNamespace(
        candidate_id="only",
        activity_posts_per_day=None,
        rank=1,
        group_id="group-only",
    )

    assert _resolve_candidate((candidate,), "lowest-volume") == "only"


def test_live_discovery_surfaces_join_results_and_reads_activity() -> None:
    result = AppDiscoveryParser().parse(
        b"""
        <main>
          <article role="article">
            <a href="/groups/member-group/">Local community London</a>
            <span>Private - 1K members - 5 posts a day</span>
          </article>
          <article role="article">
            <a href="/groups/join-group/">Local community London public</a>
            <span>Public - 2K members - 1 post a day</span>
            <button aria-label="Join Group Local community London public">Join</button>
          </article>
        </main>
        """,
        keyword="local community",
        location="London",
        source_url="https://app.invalid/groups/search/groups/",
    )

    assert [candidate.group_id for candidate in result.candidates] == ["member-group", "join-group"]
    assert result.joined_candidates[0].group_id == "member-group"
    assert result.membership_preparation_candidates[0].group_id == "join-group"
    assert result.joined_candidates[0].activity_posts_per_day == 5
