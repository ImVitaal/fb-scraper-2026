"""Fixture-backed keyword-and-location Group discovery."""

from app.discovery.parser import (
    DiscoveryCandidate,
    DiscoveryParser,
    DiscoveryResult,
    UnsupportedDiscoveryLayoutError,
)
from app.discovery.session_fixture import SessionDiscoveryFixtureAdapter

__all__ = [
    "DiscoveryCandidate",
    "DiscoveryParser",
    "DiscoveryResult",
    "SessionDiscoveryFixtureAdapter",
    "UnsupportedDiscoveryLayoutError",
]
