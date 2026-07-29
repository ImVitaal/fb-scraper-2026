"""Tests for fixture-backed keyword-and-location Group discovery."""

from __future__ import annotations

import pytest

from app.discovery import DiscoveryParser, UnsupportedDiscoveryLayoutError


def test_parser_returns_candidates_ranked_by_keyword_and_location_score() -> None:
    html = b"""
    <section data-pgscan-discovery="1" data-keyword="garden" data-location="Bristol">
      <article data-pgscan-candidate="1" data-group-id="garden-low"
        data-canonical-url="https://example.test/groups/garden-low"
        data-name="Bristol Garden Notes" data-keyword-score="0.8"
        data-location-score="0.4"></article>
      <article data-pgscan-candidate="1" data-group-id="garden-top"
        data-canonical-url="https://example.test/groups/garden-top"
        data-name="Bristol Gardeners" data-keyword-score="0.9" data-location-score="1.0"></article>
      <article data-pgscan-candidate="1" data-group-id="garden-middle"
        data-canonical-url="https://example.test/groups/garden-middle"
        data-name="Garden Society Bristol" data-keyword-score="0.95"
        data-location-score="0.6"></article>
    </section>
    """

    result = DiscoveryParser().parse(html, keyword="garden", location="Bristol")

    assert result.keyword == "garden"
    assert result.location == "Bristol"
    assert [(candidate.group_id, candidate.rank) for candidate in result.candidates] == [
        ("garden-top", 1),
        ("garden-middle", 2),
        ("garden-low", 3),
    ]
    assert result.candidates[0].score == pytest.approx(0.95)


def test_parser_rejects_query_mismatch_and_duplicate_group_ids() -> None:
    mismatch = b"""
    <section data-pgscan-discovery="1" data-keyword="garden" data-location="Bath">
      <article data-pgscan-candidate="1" data-group-id="garden-1"
        data-canonical-url="https://example.test/groups/garden-1"
        data-name="Gardeners" data-keyword-score="1" data-location-score="1"></article>
    </section>
    """
    duplicate = b"""
    <section data-pgscan-discovery="1" data-keyword="garden" data-location="Bristol">
      <article data-pgscan-candidate="1" data-group-id="garden-1"
        data-canonical-url="https://example.test/groups/garden-1"
        data-name="Gardeners" data-keyword-score="1" data-location-score="1"></article>
      <article data-pgscan-candidate="1" data-group-id="garden-1"
        data-canonical-url="https://example.test/groups/garden-1"
        data-name="Gardeners Again" data-keyword-score="1" data-location-score="1"></article>
    </section>
    """

    with pytest.raises(UnsupportedDiscoveryLayoutError, match="query markers do not match"):
        DiscoveryParser().parse(mismatch, keyword="garden", location="Bristol")
    with pytest.raises(UnsupportedDiscoveryLayoutError, match="duplicate group identity"):
        DiscoveryParser().parse(duplicate, keyword="garden", location="Bristol")


@pytest.mark.parametrize(
    "html, message",
    [
        (b"<html><body>unsupported</body></html>", "discovery anchor"),
        (
            b"""
            <section data-pgscan-discovery="1" data-keyword="garden" data-location="Bristol">
              <article data-pgscan-candidate="1" data-group-id="garden-1"
                data-canonical-url="https://example.test/groups/garden-1"
                data-name="Gardeners" data-keyword-score="1.2" data-location-score="1"></article>
            </section>
            """,
            "score marker",
        ),
    ],
)
def test_parser_rejects_unsupported_layouts(html: bytes, message: str) -> None:
    with pytest.raises(UnsupportedDiscoveryLayoutError, match=message):
        DiscoveryParser().parse(html, keyword="garden", location="Bristol")
