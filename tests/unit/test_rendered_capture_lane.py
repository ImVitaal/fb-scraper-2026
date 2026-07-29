"""Unit coverage for rendered page capture contracts."""

from __future__ import annotations

import pytest

from app.capture.rendered import RenderedPage


def test_rendered_page_requires_raw_html_bytes() -> None:
    """A rendered page always carries raw bytes for raw-first persistence."""
    page = RenderedPage(raw_html=b"<main>fixture</main>", next_cursor="cursor-2")

    assert page.raw_html == b"<main>fixture</main>"
    assert page.next_cursor == "cursor-2"

    with pytest.raises(ValueError, match="raw_html"):
        RenderedPage(raw_html=b"", next_cursor=None)


def test_rendered_page_rejects_blank_next_cursor() -> None:
    """Terminal pages use None instead of an ambiguous blank cursor."""
    with pytest.raises(ValueError, match="next_cursor"):
        RenderedPage(raw_html=b"<main>fixture</main>", next_cursor=" ")
