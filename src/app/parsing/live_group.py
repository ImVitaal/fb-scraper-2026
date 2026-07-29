"""Strict parser for the supported live Group HTML fixture layout."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.contracts.models import (
    CollectionHealth,
    CommentRecord,
    FieldProvenance,
    GroupRecord,
    MediaReference,
    PostRecord,
    SessionClass,
)


class UnsupportedLayoutError(ValueError):
    """Raised when captured HTML lacks the versioned supported layout anchors."""


class LiveGroupParser:
    """Normalize one supported live Group HTML capture without collecting replies."""

    def parse(
        self,
        raw_html: bytes,
        *,
        source_url: str,
        capture_id: str,
        raw_sha256: str,
        session_class: str,
    ) -> tuple[GroupRecord, list[PostRecord], list[CommentRecord]]:
        soup = BeautifulSoup(raw_html, "lxml")
        group_tag = self._one(soup, "[data-pgscan-group='1']", "group")
        group_id = self._required(group_tag, "data-group-id")
        group = GroupRecord.model_validate(
            self._evidence(
                {
                    "group_id": group_id,
                    "canonical_url": self._required(group_tag, "data-canonical-url"),
                    "name": self._required(group_tag, "data-name"),
                    "privacy": self._required(group_tag, "data-privacy"),
                    "membership_state": self._required(group_tag, "data-membership-state"),
                    "description": self._required(group_tag, "data-description"),
                    "member_count": self._number(group_tag, "data-member-count"),
                    "observed_at": self._required(group_tag, "data-observed-at"),
                },
                source_url,
                capture_id,
                raw_sha256,
                session_class,
                "group",
            )
        )
        posts: list[PostRecord] = []
        comments: list[CommentRecord] = []
        for post_tag in group_tag.select("[data-pgscan-post='1']"):
            if not isinstance(post_tag, Tag):
                continue
            post = PostRecord.model_validate(
                self._evidence(
                    {
                        "post_id": self._required(post_tag, "data-post-id"),
                        "group_id": self._required(post_tag, "data-group-id"),
                        "canonical_url": self._required(post_tag, "data-canonical-url"),
                        "author_id": self._required(post_tag, "data-author-id"),
                        "author_name": self._required(post_tag, "data-author-name"),
                        "published_at": self._required(post_tag, "data-published-at"),
                        "observed_at": self._required(post_tag, "data-observed-at"),
                        "text": self._text(post_tag),
                        "post_type": self._required(post_tag, "data-post-type"),
                        "media": self._media(post_tag, source_url),
                        "reactions": self._reactions(post_tag),
                        "comments_count": self._number(post_tag, "data-comments-count"),
                        "shares_count": self._number(post_tag, "data-shares-count"),
                    },
                    source_url,
                    capture_id,
                    raw_sha256,
                    session_class,
                    "post",
                )
            )
            if post.group_id != group_id:
                raise UnsupportedLayoutError("post group identity mismatch")
            posts.append(post)
            for comment_tag in group_tag.select("[data-pgscan-comment='1']"):
                if (
                    not isinstance(comment_tag, Tag)
                    or comment_tag.has_attr("data-parent-comment-id")
                    or comment_tag.get("data-post-id") != post.post_id
                ):
                    continue
                comment = CommentRecord.model_validate(
                    self._evidence(
                        {
                            "comment_id": self._required(comment_tag, "data-comment-id"),
                            "post_id": self._required(comment_tag, "data-post-id"),
                            "group_id": self._required(comment_tag, "data-group-id"),
                            "author_id": self._required(comment_tag, "data-author-id"),
                            "author_name": self._required(comment_tag, "data-author-name"),
                            "published_at": self._required(comment_tag, "data-published-at"),
                            "observed_at": self._required(comment_tag, "data-observed-at"),
                            "text": self._text(comment_tag),
                            "media": self._media(comment_tag, source_url),
                            "reactions": self._reactions(comment_tag),
                        },
                        source_url,
                        capture_id,
                        raw_sha256,
                        session_class,
                        "comment",
                    )
                )
                if comment.post_id != post.post_id or comment.group_id != group_id:
                    raise UnsupportedLayoutError("comment parent identity mismatch")
                comments.append(comment)
        return group, posts, comments

    @staticmethod
    def _one(soup: BeautifulSoup, selector: str, name: str) -> Tag:
        values = soup.select(selector)
        if len(values) != 1 or not isinstance(values[0], Tag):
            raise UnsupportedLayoutError(f"supported {name} anchor missing or ambiguous")
        return values[0]

    @staticmethod
    def _required(tag: Tag, key: str) -> str:
        value = tag.get(key)
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedLayoutError(f"required marker missing: {key}")
        return value.strip()

    def _number(self, tag: Tag, key: str) -> int:
        try:
            value = int(self._required(tag, key))
        except ValueError as error:
            raise UnsupportedLayoutError(f"invalid integer marker: {key}") from error
        if value < 0:
            raise UnsupportedLayoutError(f"negative integer marker: {key}")
        return value

    @staticmethod
    def _text(tag: Tag) -> str:
        value = tag.select_one("[data-pgscan-text='1']")
        if value is None:
            raise UnsupportedLayoutError("required text marker missing")
        text = value.get_text(strip=True)
        if not text:
            raise UnsupportedLayoutError("required text is empty")
        return text

    def _media(self, tag: Tag, source_url: str) -> list[MediaReference]:
        return [
            MediaReference(
                media_type=self._required(media, "data-pgscan-media"),
                source_url=urljoin(source_url, self._required(media, "src")),
                alt_text=str(media.get("alt")) if media.get("alt") else None,
            )
            for media in tag.select("[data-pgscan-media]")
            if isinstance(media, Tag)
        ]

    def _reactions(self, tag: Tag) -> dict[str, int]:
        return {
            key.removeprefix("data-reaction-"): self._number(tag, key)
            for key in tag.attrs
            if key.startswith("data-reaction-")
        }

    @staticmethod
    def _evidence(
        data: dict[str, Any],
        source_url: str,
        capture_id: str,
        raw_sha256: str,
        session_class: str,
        path: str,
    ) -> dict[str, Any]:
        data.update(
            {
                "schema_version": "1.0",
                "adapter_name": "playwright_group",
                "adapter_version": "1.0",
                "parser_version": "live_group_html/1.0",
                "collected_at": data["observed_at"],
                "raw_capture_id": capture_id,
                "raw_sha256": raw_sha256,
                "source_url": source_url,
                "session_class": SessionClass(session_class),
                "visibility_context": "operator_visible_group",
                "field_provenance": {
                    name: FieldProvenance(source_path=f"css={path}:{name}", confidence=1.0)
                    for name, value in data.items()
                    if value is not None
                },
                "null_reasons": {},
                "collection_health": CollectionHealth.OBSERVED,
                "availability": CollectionHealth.OBSERVED,
            }
        )
        return data
