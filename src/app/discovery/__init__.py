"""Fixture-backed keyword-and-location Group discovery."""

from app.discovery.parser import (
    DiscoveryCandidate,
    DiscoveryParser,
    DiscoveryResult,
    UnsupportedDiscoveryLayoutError,
)

__all__ = [
    "DiscoveryCandidate",
    "DiscoveryParser",
    "DiscoveryResult",
    "UnsupportedDiscoveryLayoutError",
]
