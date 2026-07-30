"""Phase 4F coverage for reusing completed Post identifiers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from bs4 import BeautifulSoup

from app.capture.playwright_adapter import BrowserCaptureLimits, PlaywrightGroupCaptureAdapter

FIXTURE = Path(__file__).parents[1] / "fixtures" / "phase4b_browser" / "dynamic_group.html"


@pytest.mark.integration
def test_known_post_is_pruned_while_new_post_is_completed(tmp_path: Path) -> None:
    """A known Post is absent while one new Post receives both interactions."""
    fixture = tmp_path / "mixed-posts.html"
    fixture.write_text(
        """
        <!doctype html><html><body>
          <main data-pgscan-content-ready="true">
            <article data-pgscan-post-id="post-known">
              <a href="/groups/1/posts/post-known">Known</a>
              <button data-pgscan-expand-post="post-known" onclick="this.remove()">See more</button>
              <button data-pgscan-expand-comments="post-known"
                onclick="this.remove()">View comments</button>
            </article>
            <article data-pgscan-post-id="post-new">
              <a href="/groups/1/posts/post-new">New</a>
              <button data-pgscan-expand-post="post-new" onclick="this.remove()">See more</button>
              <button data-pgscan-expand-comments="post-new"
                onclick="this.remove()">View comments</button>
            </article>
            <div data-pgscan-content-end="true"></div>
          </main>
        </body></html>
        """,
        encoding="utf-8",
    )
    adapter = PlaywrightGroupCaptureAdapter(
        {"cookies": [], "origins": []},
        known_post_ids={"post-known"},
    )

    with adapter.capture_pages(
        fixture.resolve().as_uri(),
        lower_bound=datetime(2026, 6, 30, tzinfo=UTC),
    ) as capture:
        cursor = None
        while True:
            page = capture(cursor)
            cursor = page.next_cursor
            if cursor is None:
                break
        interactions = cast(Any, capture)._interaction_count

    assert b"post-known" not in page.raw_html
    assert b"post-new" in page.raw_html
    assert interactions == 2
    assert adapter.protection_telemetry["known_posts_skipped"] == 1


@pytest.mark.integration
def test_thirty_post_limit_prunes_post_31_and_caps_expansion_actions(tmp_path: Path) -> None:
    """The first-run ceiling returns 30 Posts and performs at most 60 expansions."""
    articles = "\n".join(
        f"""
        <article data-pgscan-post-id="post-{index:02d}">
          <a href="/groups/1/posts/post-{index:02d}">Post {index:02d}</a>
          <button data-pgscan-expand-post="post-{index:02d}"
            onclick="this.remove()">See more</button>
          <button data-pgscan-expand-comments="post-{index:02d}"
            onclick="this.remove()">View comments</button>
        </article>
        """
        for index in range(31)
    )
    fixture = tmp_path / "thirty-one-posts.html"
    fixture.write_text(
        f"""
        <!doctype html><html><body>
          <main data-pgscan-content-ready="true">
            {articles}
            <div data-pgscan-content-end="true"></div>
          </main>
        </body></html>
        """,
        encoding="utf-8",
    )
    adapter = PlaywrightGroupCaptureAdapter(
        {"cookies": [], "origins": []},
        limits=BrowserCaptureLimits(max_pages=100, max_recent_posts=30),
    )

    with adapter.capture_pages(fixture.resolve().as_uri()) as capture:
        cursor = None
        while True:
            page = capture(cursor)
            cursor = page.next_cursor
            if cursor is None:
                break
        interactions = cast(Any, capture)._interaction_count

    parsed = BeautifulSoup(page.raw_html, "lxml")
    assert len(parsed.select("article[data-pgscan-post-id]")) == 30
    assert parsed.select_one("[data-pgscan-post-id='post-30']") is None
    assert interactions == 60
