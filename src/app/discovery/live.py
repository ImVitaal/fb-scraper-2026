"""Explicit live and fixture capture adapters for APP Group discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote_plus, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.capture import BrowserStateError
from app.discovery.parser import (
    DiscoveryCandidate,
    DiscoveryResult,
    UnsupportedDiscoveryLayoutError,
)

_GROUP_PATH = re.compile(r"^/groups/([^/?#]+)/?$")
_POSTS_PER_DAY = re.compile(r"\b(\d+)\+?\s+posts?\s+a\s+day\b", re.IGNORECASE)


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
    protection: dict[str, object]


class SessionDiscoveryAdapter:
    """Capture keyword-and-location results through an active browser page."""

    def __init__(
        self,
        *,
        mode: str | DiscoveryMode,
        base_url: str | None = None,
        navigation_delay_seconds: float = 0.0,
        retry_delays_seconds: tuple[float, ...] = (),
        max_retries: int = 0,
    ) -> None:
        self.mode = DiscoveryMode(mode)
        self.base_url = base_url.rstrip("/") if base_url is not None else None
        self.navigation_delay_seconds = navigation_delay_seconds
        self.retry_delays_seconds = retry_delays_seconds
        self.max_retries = max_retries
        self._retry_count = 0
        self._retry_waits: list[float] = []
        self._stop_reason: str | None = None
        if self.mode is DiscoveryMode.LIVE and self.base_url is None:
            raise ValueError("live discovery requires base_url")
        if self.mode is DiscoveryMode.FIXTURE and self.base_url is not None:
            raise ValueError("fixture discovery does not accept base_url")
        if navigation_delay_seconds < 0:
            raise ValueError("navigation_delay_seconds must be zero or greater")
        if any(delay < 0 for delay in retry_delays_seconds):
            raise ValueError("retry_delays_seconds values must be zero or greater")
        if max_retries < 0:
            raise ValueError("max_retries must be zero or greater")

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
                protection=self.protection_telemetry,
            )
        if page is None or fixture is not None:
            raise ValueError("live discovery requires only page")
        self._reset_telemetry()
        assert self.base_url is not None
        query = quote_plus(f"{keyword} {location}")
        encoded_location = quote_plus(location)
        source_url = f"{self.base_url}/groups/search/groups/?q={query}&location={encoded_location}"
        self._observe_responses(page)
        self._navigate(page, source_url)
        self._wait(page, self.navigation_delay_seconds)
        self._raise_if_stopped(page)
        raw_html = page.content().encode("utf-8")
        if not raw_html:
            raise UnsupportedDiscoveryLayoutError("live discovery returned empty HTML")
        return DiscoveryCapture(
            raw_html=raw_html,
            source_url=source_url,
            mode=self.mode,
            protection=self.protection_telemetry,
        )

    @property
    def protection_telemetry(self) -> dict[str, object]:
        """Return stable non-private pacing, retry, and stop evidence."""
        return {
            "delays_seconds": {"navigation": self.navigation_delay_seconds},
            "retry_count": self._retry_count,
            "retry_waits_seconds": list(self._retry_waits),
            "stop_reason": self._stop_reason,
        }

    def _navigate(self, page: DiscoveryPage, source_url: str) -> None:
        errors: list[PlaywrightError] = []
        for attempt in range(self.max_retries + 1):
            self._raise_if_stopped(page)
            try:
                page.goto(source_url, wait_until="domcontentloaded")
                self._raise_if_stopped(page)
                return
            except (PlaywrightTimeoutError, PlaywrightError) as error:
                errors.append(error)
                self._raise_if_stopped(page)
                if attempt >= self.max_retries:
                    break
                delay = self._retry_delay(attempt)
                self._retry_count += 1
                self._retry_waits.append(delay)
                self._wait(page, delay)
        raise BrowserStateError(
            "navigation_failed",
            f"discovery navigation failed after {len(errors)} attempt(s)",
        ) from errors[-1]

    def _retry_delay(self, attempt: int) -> float:
        if not self.retry_delays_seconds:
            return 0.0
        return self.retry_delays_seconds[min(attempt, len(self.retry_delays_seconds) - 1)]

    @staticmethod
    def _wait(page: DiscoveryPage, seconds: float) -> None:
        if seconds <= 0:
            return
        wait_for_timeout = getattr(page, "wait_for_timeout", None)
        if not callable(wait_for_timeout):
            raise TypeError("protected live discovery page must support wait_for_timeout")
        wait_for_timeout(seconds * 1000)

    def _observe_responses(self, page: DiscoveryPage) -> None:
        on = getattr(page, "on", None)
        if callable(on):
            on("response", self._on_response)

    def _on_response(self, response: Any) -> None:
        status = getattr(response, "status", None)
        if status in {401, 403, 429} and self._stop_reason is None:
            self._stop_reason = f"http_{status}"

    def _raise_if_stopped(self, page: DiscoveryPage) -> None:
        if self._stop_reason is not None:
            raise BrowserStateError(
                self._stop_reason,
                "discovery browser reported an immediate stop state",
            )
        failure = self._classify_failure(page)
        if failure is None:
            return
        self._stop_reason = failure
        raise BrowserStateError(
            failure,
            "discovery browser reported an immediate stop state",
        )

    @staticmethod
    def _classify_failure(page: DiscoveryPage) -> str | None:
        url_value = getattr(page, "url", "")
        url = url_value.lower() if isinstance(url_value, str) else ""
        locator = getattr(page, "locator", None)
        if not callable(locator):
            return None
        body = locator("body").inner_text(timeout=1_000).lower()
        conditions = (
            (
                "login_required",
                "[data-pgscan-login-required], form input[type='password']",
                ("/login",),
                ("log in", "login"),
            ),
            (
                "challenge",
                "[data-pgscan-challenge]",
                ("/challenge", "/checkpoint", "/captcha"),
                ("security check", "confirm your identity", "captcha", "checkpoint"),
            ),
            (
                "restricted",
                "[data-pgscan-restricted]",
                ("/restricted", "/locked"),
                (
                    "account temporarily restricted",
                    "account restricted",
                    "account locked",
                    "temporarily blocked",
                ),
            ),
        )
        for failure_class, selector, url_parts, text_parts in conditions:
            if (
                locator(selector).count()
                or any(part in url for part in url_parts)
                or any(part in body for part in text_parts)
            ):
                return failure_class
        return None

    def _reset_telemetry(self) -> None:
        self._retry_count = 0
        self._retry_waits.clear()
        self._stop_reason = None

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
        found: dict[str, tuple[str, str, tuple[str, ...], float, float, int | None]] = {}
        candidate_links_seen = 0
        join_controls_seen = 0
        for link in soup.select("main a[href*='/groups/']"):
            if not isinstance(link, Tag):
                continue
            absolute = urljoin(source_url, self._required_href(link))
            parts = urlsplit(absolute)
            match = _GROUP_PATH.fullmatch(parts.path.rstrip("/"))
            if match is None:
                continue
            candidate_links_seen += 1
            group_id = match.group(1)
            canonical_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
            name = link.get_text(" ", strip=True)
            if not name:
                raise UnsupportedDiscoveryLayoutError("Group candidate name is missing")
            container = link.find_parent(attrs={"role": ("listitem", "article")}) or link.parent
            visible = container.get_text(" ", strip=True) if isinstance(container, Tag) else name
            if isinstance(container, Tag) and any(
                button.get_text(" ", strip=True).casefold() == "join"
                or str(button.get("aria-label", "")).casefold().startswith("join group")
                for button in container.select("button")
            ):
                join_controls_seen += 1
                continue
            keyword_score = self._token_score(keyword, visible)
            location_score = self._token_score(location, visible)
            activity_match = _POSTS_PER_DAY.search(visible)
            activity = int(activity_match.group(1)) if activity_match is not None else None
            evidence = tuple(
                item
                for item, score in (
                    (f"keyword:{keyword}", keyword_score),
                    (f"location:{location}", location_score),
                )
                if score > 0
            )
            candidate = (canonical_url, name, evidence, keyword_score, location_score, activity)
            previous = found.get(group_id)
            if previous is not None and previous[0] != candidate[0]:
                raise UnsupportedDiscoveryLayoutError(
                    f"conflicting duplicate Group candidate: {group_id}"
                )
            if previous is None or len(name) < len(previous[1]):
                found[group_id] = candidate
        if not found:
            if candidate_links_seen and join_controls_seen == candidate_links_seen:
                raise UnsupportedDiscoveryLayoutError(
                    "no joined Group matches keyword and location; "
                    "membership preparation is required before collection"
                )
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
                activity_posts_per_day=value[5],
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
