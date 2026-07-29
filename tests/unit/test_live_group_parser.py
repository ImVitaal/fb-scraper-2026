"""Strict parser tests for supported live Group HTML layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.parsing.live_group import LiveGroupParser, UnsupportedLayoutError

FIXTURE = Path(__file__).parents[1] / "fixtures" / "live_group_pages" / "group.html"


def test_live_parser_normalizes_group_posts_media_and_top_level_comments() -> None:
    group, posts, comments = LiveGroupParser().parse(
        FIXTURE.read_bytes(),
        source_url="https://example.test/groups/group-live",
        capture_id="capture-live",
        raw_sha256="a" * 64,
        session_class="fixture",
    )

    assert group.group_id == "group-live"
    assert posts[0].post_id == "post-live"
    assert str(posts[0].media[0].source_url) == "https://example.test/media/post.jpg"
    assert [comment.comment_id for comment in comments] == ["comment-live"]


def test_live_parser_rejects_unsupported_layout() -> None:
    with pytest.raises(UnsupportedLayoutError):
        LiveGroupParser().parse(
            b"<html><body>unsupported</body></html>",
            source_url="https://example.test/groups/group-live",
            capture_id="capture-live",
            raw_sha256="a" * 64,
            session_class="fixture",
        )
