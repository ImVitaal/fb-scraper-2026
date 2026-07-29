"""Contracts for bounded rendered-page capture."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedPage:
    """One rendered HTML page and its optional next-page cursor."""

    raw_html: bytes
    next_cursor: str | None

    def __post_init__(self) -> None:
        if not self.raw_html:
            raise ValueError("raw_html must be non-empty")
        if self.next_cursor is not None and not self.next_cursor.strip():
            raise ValueError("next_cursor must be non-blank or None")


RenderedPageCapture = Callable[[str | None], RenderedPage]

__all__ = ["RenderedPage", "RenderedPageCapture"]
