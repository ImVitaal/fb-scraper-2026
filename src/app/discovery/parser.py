"""Strict parser for the supported keyword-and-location discovery HTML layout."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag


class UnsupportedDiscoveryLayoutError(ValueError):
    """Raised when a capture lacks the versioned discovery layout anchors."""


@dataclass(frozen=True)
class DiscoveryCandidate:
    """One ranked Group candidate from a discovery capture."""

    group_id: str
    canonical_url: str
    name: str
    keyword_score: float
    location_score: float
    score: float
    rank: int
    matching_evidence: tuple[str, ...] = ()
    activity_posts_per_day: int | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a non-secret operator-facing representation."""
        return self.__dict__.copy()


@dataclass(frozen=True)
class DiscoveryResult:
    """The candidates returned for one exact keyword-and-location query."""

    keyword: str
    location: str
    candidates: tuple[DiscoveryCandidate, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a non-secret operator-facing representation."""
        return {
            "keyword": self.keyword,
            "location": self.location,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
        }


class DiscoveryParser:
    """Parse and rank the one supported synthetic discovery HTML layout."""

    def parse(self, raw_html: bytes, *, keyword: str, location: str) -> DiscoveryResult:
        """Return candidates ranked by the mean keyword and location match score."""
        normalized_keyword = self._query_value(keyword, "keyword")
        normalized_location = self._query_value(location, "location")
        soup = BeautifulSoup(raw_html, "lxml")
        root = self._one(soup, "[data-pgscan-discovery='1']", "discovery")
        if (
            self._required(root, "data-keyword") != normalized_keyword
            or self._required(root, "data-location") != normalized_location
        ):
            raise UnsupportedDiscoveryLayoutError("discovery query markers do not match input")

        candidates = [self._candidate(tag) for tag in root.select("[data-pgscan-candidate='1']")]
        self._require_unique_identities(candidates)
        ranked = sorted(
            candidates, key=lambda item: (-item.score, item.name.casefold(), item.group_id)
        )
        return DiscoveryResult(
            keyword=normalized_keyword,
            location=normalized_location,
            candidates=tuple(
                DiscoveryCandidate(
                    group_id=candidate.group_id,
                    canonical_url=candidate.canonical_url,
                    name=candidate.name,
                    keyword_score=candidate.keyword_score,
                    location_score=candidate.location_score,
                    score=candidate.score,
                    rank=index,
                )
                for index, candidate in enumerate(ranked, start=1)
            ),
        )

    @classmethod
    def _candidate(cls, tag: Tag) -> DiscoveryCandidate:
        group_id = cls._required(tag, "data-group-id")
        canonical_url = cls._canonical_url(cls._required(tag, "data-canonical-url"), group_id)
        name = cls._required(tag, "data-name")
        keyword_score = cls._score(tag, "data-keyword-score")
        location_score = cls._score(tag, "data-location-score")
        return DiscoveryCandidate(
            group_id=group_id,
            canonical_url=canonical_url,
            name=name,
            keyword_score=keyword_score,
            location_score=location_score,
            score=(keyword_score + location_score) / 2,
            rank=0,
        )

    @staticmethod
    def _one(soup: BeautifulSoup, selector: str, name: str) -> Tag:
        values = soup.select(selector)
        if len(values) != 1 or not isinstance(values[0], Tag):
            raise UnsupportedDiscoveryLayoutError(f"supported {name} anchor missing or ambiguous")
        return values[0]

    @staticmethod
    def _required(tag: Tag, key: str) -> str:
        value = tag.get(key)
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedDiscoveryLayoutError(f"required marker missing: {key}")
        return value.strip()

    @classmethod
    def _score(cls, tag: Tag, key: str) -> float:
        try:
            value = float(cls._required(tag, key))
        except ValueError as error:
            raise UnsupportedDiscoveryLayoutError(f"invalid score marker: {key}") from error
        if not 0 <= value <= 1:
            raise UnsupportedDiscoveryLayoutError(f"score marker must be between 0 and 1: {key}")
        return value

    @staticmethod
    def _query_value(value: str, name: str) -> str:
        if not value.strip():
            raise ValueError(f"{name} must not be empty")
        return value.strip()

    @staticmethod
    def _canonical_url(url: str, group_id: str) -> str:
        parts = urlsplit(url)
        path_parts = [part for part in parts.path.split("/") if part]
        if (
            parts.scheme != "https"
            or not parts.netloc
            or path_parts != ["groups", group_id]
            or not group_id.replace("-", "").replace("_", "").isalnum()
        ):
            raise UnsupportedDiscoveryLayoutError("invalid candidate canonical URL")
        return urlunsplit(("https", parts.netloc.lower(), f"/groups/{group_id}", "", ""))

    @staticmethod
    def _require_unique_identities(candidates: list[DiscoveryCandidate]) -> None:
        group_ids = [candidate.group_id for candidate in candidates]
        canonical_urls = [candidate.canonical_url for candidate in candidates]
        if len(group_ids) != len(set(group_ids)) or len(canonical_urls) != len(set(canonical_urls)):
            raise UnsupportedDiscoveryLayoutError("duplicate group identity")
