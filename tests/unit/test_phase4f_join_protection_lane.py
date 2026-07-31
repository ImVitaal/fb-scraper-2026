"""Phase 4F isolated protection coverage for keyword-selected membership actions."""

from __future__ import annotations

import pytest

from app.protection_join import (
    AccountStopError,
    JoinActionGuard,
    JoinActionLimitError,
    KeywordMatchError,
)


def test_guard_allows_one_matching_unattempted_group_and_records_it() -> None:
    guard = JoinActionGuard()

    action = guard.reserve(
        "group-101",
        matches_keyword=True,
        matches_location=True,
    )

    assert action.group_id == "group-101"
    assert action.ordinal == 1
    assert action.pacing_delay_seconds == (10.0, 20.0)
    assert guard.attempted_group_ids == frozenset({"group-101"})


def test_guard_blocks_a_repeated_group_before_any_second_action() -> None:
    guard = JoinActionGuard()
    guard.reserve("group-101", matches_keyword=True, matches_location=True)

    with pytest.raises(JoinActionLimitError, match="already attempted"):
        guard.reserve("group-101", matches_keyword=True, matches_location=True)


def test_guard_blocks_a_second_group_in_the_same_run() -> None:
    guard = JoinActionGuard()
    guard.reserve("group-101", matches_keyword=True, matches_location=True)

    with pytest.raises(JoinActionLimitError, match="one membership action"):
        guard.reserve("group-102", matches_keyword=True, matches_location=True)


@pytest.mark.parametrize(
    ("matches_keyword", "matches_location"),
    [(False, True), (True, False), (False, False)],
)
def test_guard_requires_keyword_and_location_match(
    matches_keyword: bool,
    matches_location: bool,
) -> None:
    guard = JoinActionGuard()

    with pytest.raises(KeywordMatchError, match="keyword and location"):
        guard.reserve(
            "group-101",
            matches_keyword=matches_keyword,
            matches_location=matches_location,
        )


@pytest.mark.parametrize(
    "stop_reason",
    ["login_required", "challenge", "restricted", "http_401", "http_403", "http_429"],
)
def test_guard_stops_before_join_when_account_stop_is_observed(stop_reason: str) -> None:
    guard = JoinActionGuard()

    with pytest.raises(AccountStopError, match=stop_reason):
        guard.reserve(
            "group-101",
            matches_keyword=True,
            matches_location=True,
            account_stop_reason=stop_reason,
        )

    assert guard.attempted_group_ids == frozenset()


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param(((9.0, 20.0), 1), id="pacing-below-minimum"),
        pytest.param(((10.0, 21.0), 1), id="pacing-above-maximum"),
        pytest.param(((10.0, 20.0), 2), id="more-than-one-action"),
    ],
)
def test_policy_rejects_unprotected_bounds(policy: tuple[tuple[float, float], int]) -> None:
    from app.protection_join import JoinProtectionPolicy

    with pytest.raises(ValueError):
        JoinProtectionPolicy(
            pacing_delay_seconds=policy[0],
            max_actions_per_run=policy[1],
        )


def test_guard_honors_a_prior_attempt_and_rejects_blank_identity() -> None:
    guard = JoinActionGuard(attempted_group_ids=("group-101",))

    with pytest.raises(JoinActionLimitError, match="already attempted"):
        guard.reserve("group-101", matches_keyword=True, matches_location=True)
    with pytest.raises(ValueError, match="non-empty"):
        guard.reserve("  ", matches_keyword=True, matches_location=True)
