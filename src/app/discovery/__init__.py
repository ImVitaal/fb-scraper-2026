"""Fixture-backed keyword-and-location Group discovery."""

from app.discovery.live import (
    AppDiscoveryParser,
    DiscoveryCapture,
    DiscoveryMode,
    SessionDiscoveryAdapter,
)
from app.discovery.membership import MembershipJoinAdapter, MembershipJoinOutcome
from app.discovery.parser import (
    DiscoveryCandidate,
    DiscoveryParser,
    DiscoveryResult,
    MembershipState,
    UnsupportedDiscoveryLayoutError,
)
from app.discovery.session_fixture import SessionDiscoveryFixtureAdapter

__all__ = [
    "AppDiscoveryParser",
    "DiscoveryCandidate",
    "DiscoveryCapture",
    "DiscoveryMode",
    "DiscoveryParser",
    "DiscoveryResult",
    "MembershipJoinAdapter",
    "MembershipJoinOutcome",
    "MembershipState",
    "SessionDiscoveryAdapter",
    "SessionDiscoveryFixtureAdapter",
    "UnsupportedDiscoveryLayoutError",
]
