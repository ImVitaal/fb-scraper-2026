"""Deterministic, checkpoint-first cursor pagination."""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import Protocol, TypeVar

ItemT = TypeVar("ItemT")
CursorT = TypeVar("CursorT", bound=Hashable)


class CursorPage(Protocol[ItemT, CursorT]):
    """A fetched page with items and an optional cursor for the next page."""

    @property
    def items(self) -> Sequence[ItemT]:
        """Return the page items."""

    @property
    def next_cursor(self) -> CursorT | None:
        """Return the cursor required for the next page, if one exists."""


class PageFetcher(Protocol[ItemT, CursorT]):
    """Fetch a page from the initial position or a previously checkpointed cursor."""

    def __call__(self, cursor: CursorT | None) -> CursorPage[ItemT, CursorT]:
        """Fetch one page."""


class PaginationCheckpoint(Protocol[CursorT]):
    """Durably record the cursor before its corresponding page fetch."""

    def __call__(self, cursor: CursorT, interaction_number: int) -> None:
        """Persist the next cursor and its one-based interaction number."""


class PaginationLoopError(RuntimeError):
    """Raised when a page points to a cursor that has already been fetched."""


class PageLimitExceeded(RuntimeError):
    """Raised when another page is available beyond the configured page bound."""


def paginate_pages[ItemT, CursorT: Hashable](
    fetch_page: PageFetcher[ItemT, CursorT],
    checkpoint: PaginationCheckpoint[CursorT],
    *,
    max_pages: int,
    initial_cursor: CursorT | None = None,
) -> tuple[CursorPage[ItemT, CursorT], ...]:
    """Fetch a bounded cursor sequence with durable pre-fetch checkpoints.

    The helper detects repeated cursors before a checkpoint or follow-up fetch.
    It calls ``checkpoint`` after each non-terminal page and before fetching its
    next cursor.
    """
    if max_pages <= 0:
        raise ValueError("max_pages must be greater than zero")

    cursor = initial_cursor
    seen_cursors: set[CursorT] = set()
    if initial_cursor is not None:
        seen_cursors.add(initial_cursor)
    pages: list[CursorPage[ItemT, CursorT]] = []

    while True:
        page = fetch_page(cursor)
        pages.append(page)
        next_cursor = page.next_cursor
        if next_cursor is None:
            return tuple(pages)
        if len(pages) >= max_pages:
            raise PageLimitExceeded(f"pagination exceeded max_pages={max_pages}")
        if next_cursor in seen_cursors:
            raise PaginationLoopError(f"repeated pagination cursor: {next_cursor!r}")

        interaction_number = len(pages)
        checkpoint(next_cursor, interaction_number)
        seen_cursors.add(next_cursor)
        cursor = next_cursor
