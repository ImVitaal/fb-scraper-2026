"""Unit tests for deterministic cursor pagination."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.capture.pagination import PageLimitExceeded, PaginationLoopError, paginate_pages


@dataclass(frozen=True)
class FakePage:
    """A synthetic page with a cursor for the next fetch."""

    items: tuple[str, ...]
    next_cursor: str | None


def test_paginates_all_pages_and_checkpoints_before_each_next_fetch() -> None:
    pages = {
        None: FakePage(("one",), "cursor-1"),
        "cursor-1": FakePage(("two",), "cursor-2"),
        "cursor-2": FakePage(("three",), None),
    }
    events: list[tuple[str, str, int | None]] = []

    def fetch(cursor: str | None) -> FakePage:
        events.append(("fetch", str(cursor), None))
        return pages[cursor]

    def checkpoint(cursor: str, interaction_number: int) -> None:
        events.append(("checkpoint", cursor, interaction_number))

    result = paginate_pages(fetch, checkpoint, max_pages=3)

    assert [page.items for page in result] == [("one",), ("two",), ("three",)]
    assert events == [
        ("fetch", "None", None),
        ("checkpoint", "cursor-1", 1),
        ("fetch", "cursor-1", None),
        ("checkpoint", "cursor-2", 2),
        ("fetch", "cursor-2", None),
    ]


def test_stops_before_checkpointing_or_fetching_a_repeated_cursor() -> None:
    pages = {
        None: FakePage(("one",), "cursor-1"),
        "cursor-1": FakePage(("two",), "cursor-1"),
    }
    events: list[tuple[str, str]] = []

    def fetch(cursor: str | None) -> FakePage:
        events.append(("fetch", str(cursor)))
        return pages[cursor]

    def checkpoint(cursor: str, interaction_number: int) -> None:
        del interaction_number
        events.append(("checkpoint", cursor))

    with pytest.raises(PaginationLoopError, match="cursor-1"):
        paginate_pages(fetch, checkpoint, max_pages=3)

    assert events == [
        ("fetch", "None"),
        ("checkpoint", "cursor-1"),
        ("fetch", "cursor-1"),
    ]


def test_stops_at_the_configured_page_bound_before_a_next_fetch() -> None:
    pages = {
        None: FakePage(("one",), "cursor-1"),
        "cursor-1": FakePage(("two",), "cursor-2"),
    }
    events: list[str] = []

    def fetch(cursor: str | None) -> FakePage:
        events.append(f"fetch:{cursor}")
        return pages[cursor]

    def checkpoint(cursor: str, interaction_number: int) -> None:
        events.append(f"checkpoint:{cursor}:{interaction_number}")

    with pytest.raises(PageLimitExceeded, match="max_pages=1"):
        paginate_pages(fetch, checkpoint, max_pages=1)

    assert events == ["fetch:None"]


def test_rejects_a_non_positive_page_bound() -> None:
    with pytest.raises(ValueError, match="max_pages"):
        paginate_pages(
            lambda cursor: FakePage((), cursor),
            lambda cursor, interaction_number: None,
            max_pages=0,
        )
