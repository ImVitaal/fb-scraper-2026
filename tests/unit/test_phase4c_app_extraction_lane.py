"""Phase 4C tests for versioned APP HTML extraction."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.contracts.models import NullReason, SessionClass
from app.parsing.app_group import AppGroupExtractionAdapter
from app.parsing.live_group import UnsupportedLayoutError

FIXTURE = Path(__file__).parents[1] / "fixtures" / "app_operator_redacted" / "group_page.html"


def test_app_adapter_extracts_canonical_records_media_and_top_level_comments() -> None:
    group, posts, comments = AppGroupExtractionAdapter().parse(
        FIXTURE.read_bytes(),
        source_url="https://app.invalid/groups/9100001/",
        capture_id="capture-app-redacted",
        raw_sha256="a" * 64,
        session_class=SessionClass.IMPORTED,
        observed_at=datetime(2026, 7, 30, tzinfo=UTC),
        lower_bound=datetime(2026, 7, 1, tzinfo=UTC),
    )

    assert AppGroupExtractionAdapter.adapter_version == "1.0"
    assert group.group_id == "9100001"
    assert str(group.canonical_url) == "https://app.invalid/groups/9100001"
    assert group.null_reasons == {
        "description": NullReason.NOT_PRESENT,
        "member_count": NullReason.NOT_PRESENT,
    }
    assert group.session_class is SessionClass.IMPORTED
    assert [post.post_id for post in posts] == ["9200001"]
    assert str(posts[0].canonical_url) == "https://app.invalid/groups/9100001/posts/9200001"
    assert str(posts[0].media[0].source_url) == (
        "https://app.invalid/media/redacted-image.jpg?token=none"
    )
    assert posts[0].media[0].alt_text == "REDACTED ALT TEXT"
    assert [comment.comment_id for comment in comments] == ["9300001"]
    assert comments[0].parent_comment_id is None
    assert group.field_provenance["group_id"].source_path.startswith("css=")
    assert posts[0].field_provenance["post_id"].transformation == "canonical_link_segment"


def test_app_adapter_rejects_layout_without_canonical_group_and_post_anchors() -> None:
    with pytest.raises(UnsupportedLayoutError, match="group canonical link"):
        AppGroupExtractionAdapter().parse(
            b"<main role='main'><article role='article'>REDACTED</article></main>",
            source_url="https://app.invalid/groups/9100001/",
            capture_id="capture-app-drift",
            raw_sha256="b" * 64,
            session_class=SessionClass.GUIDED_LOGIN,
            observed_at=datetime(2026, 7, 30, tzinfo=UTC),
            lower_bound=datetime(2026, 7, 1, tzinfo=UTC),
        )


def test_app_adapter_uses_group_route_and_heading_when_navigation_has_no_group_link() -> None:
    html = b"""
    <div role="main">
      <div role="main">
        <h1><span>REDACTED GROUP</span></h1>
        <nav>
          <a href="/groups/">Groups</a>
          <a href="/groups/other-group/">Other group</a>
        </nav>
        <div role="feed">
          <div role="article">
            <a href="/groups/9100001/posts/9200012/">Permalink</a>
            <time datetime="2026-07-29T12:00:00Z">REDACTED TIME</time>
            <div data-ad-preview="message">REDACTED POST TEXT</div>
          </div>
        </div>
      </div>
    </div>
    """

    group, posts, comments = AppGroupExtractionAdapter().parse(
        html,
        source_url="https://app.invalid/groups/9100001/",
        capture_id="capture-app-route-heading",
        raw_sha256="f" * 64,
        session_class=SessionClass.IMPORTED,
        observed_at=datetime(2026, 7, 30, tzinfo=UTC),
        lower_bound=datetime(2026, 7, 1, tzinfo=UTC),
    )

    assert group.group_id == "9100001"
    assert group.name == "REDACTED GROUP"
    assert str(group.canonical_url) == "https://app.invalid/groups/9100001"
    assert [post.post_id for post in posts] == ["9200012"]
    assert comments == []


def test_app_adapter_accepts_a_group_shell_before_posts_render() -> None:
    html = b"""
    <div role="main">
      <h1><span>REDACTED GROUP</span></h1>
      <nav><a href="/groups/other-group/">Other group</a></nav>
      <div role="feed"></div>
    </div>
    """

    group, posts, comments = AppGroupExtractionAdapter().parse(
        html,
        source_url="https://app.invalid/groups/9100001/",
        capture_id="capture-app-shell",
        raw_sha256="0" * 64,
        session_class=SessionClass.IMPORTED,
        observed_at=datetime(2026, 7, 30, tzinfo=UTC),
        lower_bound=datetime(2026, 7, 1, tzinfo=UTC),
    )

    assert group.group_id == "9100001"
    assert posts == []
    assert comments == []


def test_app_adapter_records_supported_nulls_and_unix_time() -> None:
    html = b"""
    <main role="main">
      <h1><a href="/groups/9100001/">REDACTED GROUP</a></h1>
      <article role="article">
        <a href="/groups/9100001/posts/9200010/">Permalink</a>
        <abbr data-utime="1785326400">REDACTED TIME</abbr>
        <video src="/media/redacted-video.mp4"></video>
        <div role="article" data-commentid="9300010">
          <a href="/groups/9100001/posts/9200010/?comment_id=9300010">Comment</a>
        </div>
      </article>
    </main>
    """

    _, posts, comments = AppGroupExtractionAdapter().parse(
        html,
        source_url="https://app.invalid/groups/9100001/",
        capture_id="capture-app-nulls",
        raw_sha256="c" * 64,
        session_class=SessionClass.GUIDED_LOGIN,
        observed_at=datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert posts[0].author_id is None
    assert posts[0].null_reasons == {
        "author_id": NullReason.NOT_PRESENT,
        "author_name": NullReason.NOT_PRESENT,
        "text": NullReason.NOT_PRESENT,
    }
    assert posts[0].media[0].media_type == "video"
    assert comments[0].null_reasons == {
        "author_id": NullReason.NOT_PRESENT,
        "author_name": NullReason.NOT_PRESENT,
        "published_at": NullReason.NOT_PRESENT,
        "text": NullReason.NOT_PRESENT,
    }


def test_app_adapter_rejects_non_operator_session_and_boundary_without_time() -> None:
    html = b"""
    <main role="main">
      <h1><a href="/groups/9100001/">REDACTED GROUP</a></h1>
      <article role="article">
        <a href="/groups/9100001/posts/9200011/">Permalink</a>
      </article>
    </main>
    """
    adapter = AppGroupExtractionAdapter()
    with pytest.raises(ValueError, match="imported or guided_login"):
        adapter.parse(
            html,
            source_url="https://app.invalid/groups/9100001/",
            capture_id="capture-app-session",
            raw_sha256="d" * 64,
            session_class=SessionClass.FIXTURE,
            observed_at=datetime(2026, 7, 30, tzinfo=UTC),
        )
    with pytest.raises(UnsupportedLayoutError, match="timestamp is required"):
        adapter.parse(
            html,
            source_url="https://app.invalid/groups/9100001/",
            capture_id="capture-app-time",
            raw_sha256="e" * 64,
            session_class=SessionClass.IMPORTED,
            observed_at=datetime(2026, 7, 30, tzinfo=UTC),
            lower_bound=datetime(2026, 7, 1, tzinfo=UTC),
        )
