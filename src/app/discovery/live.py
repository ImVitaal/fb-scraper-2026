"""Explicit live and fixture capture adapters for APP Group discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from app.discovery.parser import (
    DiscoveryCandidate,
    DiscoveryResult,
    UnsupportedDiscoveryLayoutError,
)

_GROUP_PATH = re.compile(r"^/groups/([^/?#]+)/?$")


class DiscoveryMode(StrEnum):
    """Select browser capture or deterministic fixture capture."""

    LIVE = "live"
    FIXTURE = "fixture"


class DiscoveryPage(Protocol):
    """Minimal synchronous browser page used by live discovery."""

    def goto(self, url: str, *, wait_until: str) -> object:
        """Navigate to the query URL."""

    def content(self) -> str:
        """Return the rendered HTML."""


@dataclass(frozen=True)
class DiscoveryCapture:
    """Raw discovery bytes that callers must persist before parsing."""

    raw_html: bytes
    source_url: str
    mode: DiscoveryMode


class SessionDiscoveryAdapter:
    """Capture keyword-and-location results through an active browser page."""

    def __init__(
        self,
        *,
        mode: str | DiscoveryMode,
        base_url: str | None = None,
    ) -> None:
        self.mode = DiscoveryMode(mode)
        self.base_url = base_url.rstrip("/") if base_url is not None else None
        if self.mode is DiscoveryMode.LIVE and self.base_url is None:
            raise ValueError("live discovery requires base_url")
        if self.mode is DiscoveryMode.FIXTURE and self.base_url is not None:
            raise ValueError("fixture discovery does not accept base_url")

    def capture(
        self,
        *,
        keyword: str,
        location: str,
        page: DiscoveryPage | None = None,
        fixture: Path | None = None,
    ) -> DiscoveryCapture:
        """Return raw HTML; persist it before calling ``AppDiscoveryParser``."""
        keyword = self._query(keyword, "keyword")
        location = self._query(location, "location")
        if self.mode is DiscoveryMode.FIXTURE:
            if fixture is None or page is not None:
                raise ValueError("fixture discovery requires only fixture")
            return DiscoveryCapture(
                raw_html=fixture.read_bytes(),
                source_url=fixture.resolve().as_uri(),
                mode=self.mode,
            )
        if page is None or fixture is not None:
            raise ValueError("live discovery requires only page")
        assert self.base_url is not None
        query = quote_plus(f"{keyword} {location}")
        encoded_location = quote_plus(location)
        source_url = f"{self.base_url}/groups/search/groups/?q={query}&location={encoded_location}"
        page.goto(source_url, wait_until="domcontentloaded")
        raw_html = page.content().encode("utf-8")
        if not raw_html:
            raise UnsupportedDiscoveryLayoutError("live discovery returned empty HTML")
        return DiscoveryCapture(raw_html=raw_html, source_url=source_url, mode=self.mode)

    @staticmethod
    def _query(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{name} must not be empty")
        return normalized


class AppDiscoveryParser:
    """Parse canonical Group candidates from one stored live discovery capture."""

    adapter_name = "app_discovery_html"
    adapter_version = "1.0"
    parser_version = "app_discovery_html/1.0"

    def parse(
        self,
        raw_html: bytes,
        *,
        keyword: str,
        location: str,
        source_url: str,
    ) -> DiscoveryResult:
        """Rank candidates deterministically using visible matching evidence."""
        keyword = SessionDiscoveryAdapter._query(keyword, "keyword")
        location = SessionDiscoveryAdapter._query(location, "location")
        soup = BeautifulSoup(raw_html, "lxml")
        found: dict[str, tuple[str, str, tuple[str, ...], float, float]] = {}
        for link in soup.select("main a[href*='/groups/']"):
            if not isinstance(link, Tag):
                continue
            absolute = urljoin(source_url, self._required_href(link))
            parts = urlsplit(absolute)
            match = _GROUP_PATH.fullmatch(parts.path.rstrip("/"))
            if match is None:
                continue
            group_id = match.group(1)
            canonical_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
            name = link.get_text(" ", strip=True)
            if not name:
                raise UnsupportedDiscoveryLayoutError("Group candidate name is missing")
            container = link.find_parent(attrs={"role": ("listitem", "article")}) or link.parent
            visible = container.get_text(" ", strip=True) if isinstance(container, Tag) else name
            keyword_score = self._token_score(keyword, visible)
            location_score = self._token_score(location, visible)
            evidence = tuple(
                item
                for item, score in (
                    (f"keyword:{keyword}", keyword_score),
                    (f"location:{location}", location_score),
                )
                if score > 0
            )
            candidate = (canonical_url, name, evidence, keyword_score, location_score)
            previous = found.get(group_id)
            if previous is not None and previous != candidate:
                raise UnsupportedDiscoveryLayoutError(
                    f"conflicting duplicate Group candidate: {group_id}"
                )
            found[group_id] = candidate
        if not found:
            raise UnsupportedDiscoveryLayoutError("supported Group candidates are missing")

        ordered = sorted(
            found.items(),
            key=lambda item: (
                -((item[1][3] + item[1][4]) / 2),
                item[1][1].casefold(),
                item[0],
            ),
        )
        candidates = tuple(
            DiscoveryCandidate(
                group_id=group_id,
                canonical_url=value[0],
                name=value[1],
                keyword_score=value[3],
                location_score=value[4],
                score=(value[3] + value[4]) / 2,
                rank=rank,
                matching_evidence=value[2],
            )
            for rank, (group_id, value) in enumerate(ordered, start=1)
        )
        return DiscoveryResult(keyword=keyword, location=location, candidates=candidates)

    @staticmethod
    def _required_href(tag: Tag) -> str:
        value = tag.get("href")
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedDiscoveryLayoutError("Group candidate canonical URL is missing")
        return value.strip()

    @staticmethod
    def _token_score(query: str, visible: str) -> float:
        tokens = tuple(dict.fromkeys(query.casefold().split()))
        if not tokens:
            return 0.0
        haystack = visible.casefold()
        return sum(token in haystack for token in tokens) / len(tokens)
