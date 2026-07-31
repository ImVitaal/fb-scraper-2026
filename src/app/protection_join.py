"""One-at-a-time protection primitive for keyword-selected Group membership actions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


class JoinProtectionError(RuntimeError):
    """Base error for a membership action blocked before browser interaction."""


class AccountStopError(JoinProtectionError):
    """An account-stop state was observed before the membership action."""


class JoinActionLimitError(JoinProtectionError):
    """The one-action budget or an attempted Group identity blocks the action."""


class KeywordMatchError(JoinProtectionError):
    """The candidate does not match both configured discovery terms."""


@dataclass(frozen=True)
class JoinProtectionPolicy:
    """Fixed low-volume bounds for a single keyword-selected membership action."""

    pacing_delay_seconds: tuple[float, float] = (10.0, 20.0)
    max_actions_per_run: int = 1

    def __post_init__(self) -> None:
        lower, upper = self.pacing_delay_seconds
        if lower < 10.0 or upper > 20.0 or lower > upper:
            raise ValueError("pacing_delay_seconds must remain within 10-20 seconds")
        if self.max_actions_per_run != 1:
            raise ValueError("max_actions_per_run must equal one")


DEFAULT_JOIN_PROTECTION_POLICY = JoinProtectionPolicy()


@dataclass(frozen=True)
class ReservedJoinAction:
    """A single browser action that the caller may execute after its configured delay."""

    group_id: str
    ordinal: int
    pacing_delay_seconds: tuple[float, float]


class JoinActionGuard:
    """Reserve at most one matching Group identity and never retry that identity."""

    def __init__(
        self,
        *,
        policy: JoinProtectionPolicy = DEFAULT_JOIN_PROTECTION_POLICY,
        attempted_group_ids: Iterable[str] = (),
    ) -> None:
        self.policy = policy
        self._attempted_group_ids = {self._group_id(group_id) for group_id in attempted_group_ids}
        self._actions_reserved = 0

    @property
    def attempted_group_ids(self) -> frozenset[str]:
        """Return non-private Group identities that must never receive another action."""
        return frozenset(self._attempted_group_ids)

    def reserve(
        self,
        group_id: str,
        *,
        matches_keyword: bool,
        matches_location: bool,
        account_stop_reason: str | None = None,
    ) -> ReservedJoinAction:
        """Validate and reserve one guarded membership action before browser interaction."""
        normalized_group_id = self._group_id(group_id)
        if account_stop_reason is not None:
            raise AccountStopError(f"membership action stopped: {account_stop_reason}")
        if not matches_keyword or not matches_location:
            raise KeywordMatchError("candidate must match configured keyword and location")
        if normalized_group_id in self._attempted_group_ids:
            raise JoinActionLimitError("membership action already attempted for this Group")
        if self._actions_reserved >= self.policy.max_actions_per_run:
            raise JoinActionLimitError("one membership action is permitted per run")

        self._attempted_group_ids.add(normalized_group_id)
        self._actions_reserved += 1
        return ReservedJoinAction(
            group_id=normalized_group_id,
            ordinal=self._actions_reserved,
            pacing_delay_seconds=self.policy.pacing_delay_seconds,
        )

    @staticmethod
    def _group_id(group_id: str) -> str:
        normalized = group_id.strip()
        if not normalized:
            raise ValueError("group_id must be a non-empty string")
        return normalized
