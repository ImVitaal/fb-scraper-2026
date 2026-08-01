"""Versioned extraction adapter for rendered APP Group HTML."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, TypeVar
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from app.contracts.models import (
    CanonicalRecord,
    CollectionHealth,
    CommentRecord,
    FieldProvenance,
    GroupRecord,
    MediaReference,
    NullReason,
    PostRecord,
    SessionClass,
)
from app.parsing.live_group import UnsupportedLayoutError

_GROUP_PATH = re.compile(r"^/groups/([^/?#]+)/?$")
_POST_PATH = re.compile(r"^/groups/([^/?#]+)/posts/([^/?#]+)/?$")
_INTEGER = re.compile(r"\d+")
_Record = TypeVar("_Record", bound=CanonicalRecord)


class AppGroupExtractionAdapter:
    """Extract canonical records from one supported rendered APP layout."""

    adapter_name = "app_rendered_html"
    adapter_version = "1.0"
    parser_version = "app_group_html/1.0"

    def parse(
        self,
        raw_html: bytes,
        *,
        source_url: str,
        capture_id: str,
        raw_sha256: str,
        session_class: str | SessionClass,
        observed_at: datetime,
        lower_bound: datetime | None = None,
    ) -> tuple[GroupRecord, list[PostRecord], list[CommentRecord]]:
        """Extract one Group and its in-boundary Posts and top-level Comments."""
        observed_at = self._aware(observed_at, "observed_at")
        if lower_bound is not None:
            lower_bound = self._aware(lower_bound, "lower_bound")
        parsed_session_class = SessionClass(session_class)
        if parsed_session_class not in {SessionClass.IMPORTED, SessionClass.GUIDED_LOGIN}:
            raise ValueError("APP extraction requires an imported or guided_login session class")

        soup = BeautifulSoup(raw_html, "lxml")
        group_link, group_id, group_url, used_source_route = self._group_anchor(soup, source_url)
        group_name = group_link.get_text(" ", strip=True)
        if not group_name:
            raise UnsupportedLayoutError("Group name is missing")
        group_root = group_link.find_parent("main") or soup
        description = self._optional_text(group_root, "[data-group-description]")
        member_count = self._optional_count(group_root, "[data-member-count]")
        group_data: dict[str, Any] = {
            "group_id": group_id,
            "canonical_url": group_url,
            "name": group_name,
            "privacy": "operator_visible",
            "membership_state": "visible_through_session",
            "description": description,
            "member_count": member_count,
            "observed_at": observed_at,
        }
        group_selector = (
            "css=h1::text|source_url=group_path"
            if used_source_route
            else "css=main h1 a[href*='/groups/']"
        )
        group_id_transform = "source_url_path" if used_source_route else "canonical_link_segment"
        group_url_transform = "source_url_path" if used_source_route else "canonical_url"
        group = GroupRecord.model_validate(
            self._evidence(
                group_data,
                source_url=source_url,
                capture_id=capture_id,
                raw_sha256=raw_sha256,
                session_class=parsed_session_class,
                observed_at=observed_at,
                paths={
                    "group_id": (group_selector, group_id_transform),
                    "canonical_url": (f"{group_selector}@href", group_url_transform),
                    "name": (group_selector, None),
                    "privacy": ("derived=session_visible_group", "visibility_classification"),
                    "membership_state": (
                        "derived=session_visible_group",
                        "visibility_classification",
                    ),
                    "description": ("css=[data-group-description]::text", None),
                    "member_count": ("css=[data-member-count]::text", "integer"),
                    "observed_at": ("capture=collected_at", None),
                },
                nullable=GroupRecord.nullable_fields,
            )
        )

        posts: list[PostRecord] = []
        comments: list[CommentRecord] = []
        seen_posts: dict[str, PostRecord] = {}
        seen_comments: dict[str, CommentRecord] = {}
        for post_tag, post_group_id, post_id, post_url in self._post_anchors(soup, source_url):
            if post_group_id != group_id:
                raise UnsupportedLayoutError("Post Group identity does not match captured Group")
            published_at = self._time(post_tag)
            if lower_bound is not None:
                if published_at is None:
                    raise UnsupportedLayoutError(
                        f"Post timestamp is required for the collection boundary: {post_id}"
                    )
                if published_at < lower_bound:
                    continue

            media = self._media(post_tag, source_url, owner_comment=None)
            author_id, author_name = self._author(post_tag)
            text = self._optional_text(post_tag, "[data-ad-preview='message']")
            top_level_comment_tags = self._top_level_comments(post_tag)
            post_data: dict[str, Any] = {
                "post_id": post_id,
                "group_id": group_id,
                "canonical_url": post_url,
                "author_id": author_id,
                "author_name": author_name,
                "published_at": published_at,
                "observed_at": observed_at,
                "text": text,
                "post_type": "media" if media else "text",
                "media": media,
                "reactions": {},
                "comments_count": len(top_level_comment_tags),
                "shares_count": 0,
            }
            post = PostRecord.model_validate(
                self._evidence(
                    post_data,
                    source_url=source_url,
                    capture_id=capture_id,
                    raw_sha256=raw_sha256,
                    session_class=parsed_session_class,
                    observed_at=observed_at,
                    paths=self._post_paths(),
                    nullable=PostRecord.nullable_fields,
                )
            )
            self._add_unique(seen_posts, post_id, post, "Post")
            if post not in posts:
                posts.append(post)

            for comment_tag in top_level_comment_tags:
                comment_id = self._comment_id(comment_tag, group_id, post_id)
                comment_author_id, comment_author_name = self._author(comment_tag)
                comment_data: dict[str, Any] = {
                    "comment_id": comment_id,
                    "post_id": post_id,
                    "group_id": group_id,
                    "parent_comment_id": None,
                    "author_id": comment_author_id,
                    "author_name": comment_author_name,
                    "published_at": self._time(comment_tag),
                    "observed_at": observed_at,
                    "text": self._optional_text(comment_tag, "[data-ad-preview='comment']"),
                    "media": self._media(comment_tag, source_url, owner_comment=comment_tag),
                    "reactions": {},
                }
                comment = CommentRecord.model_validate(
                    self._evidence(
                        comment_data,
                        source_url=source_url,
                        capture_id=capture_id,
                        raw_sha256=raw_sha256,
                        session_class=parsed_session_class,
                        observed_at=observed_at,
                        paths=self._comment_paths(),
                        nullable=CommentRecord.nullable_fields,
                    )
                )
                self._add_unique(seen_comments, comment_id, comment, "Comment")
                if comment not in comments:
                    comments.append(comment)
        if not posts and not self._has_post_anchor(soup) and not used_source_route:
            raise UnsupportedLayoutError("supported Post canonical anchors are missing")
        return group, posts, comments

    @classmethod
    def _group_anchor(cls, soup: BeautifulSoup, source_url: str) -> tuple[Tag, str, str, bool]:
        matches: list[tuple[Tag, str, str]] = []
        for link in soup.select("main h1 a[href], main a[href]"):
            if not isinstance(link, Tag):
                continue
            canonical = cls._canonical_url(source_url, cls._required_href(link))
            match = _GROUP_PATH.fullmatch(urlsplit(canonical).path)
            if match:
                matches.append((link, match.group(1), canonical))
        source_canonical = cls._canonical_url(source_url, source_url)
        source_match = _GROUP_PATH.fullmatch(urlsplit(source_canonical).path)
        if source_match:
            source_group_id = source_match.group(1)
            source_matches = [item for item in matches if item[1] == source_group_id]
            source_identities = {(group_id, canonical) for _, group_id, canonical in source_matches}
            if len(source_identities) == 1:
                group_id, canonical = source_identities.pop()
                link = next(item for item, item_id, _ in source_matches if item_id == group_id)
                return link, group_id, canonical, False
            if not source_matches:
                headings = soup.select("h1")
                if (
                    len(headings) == 1
                    and isinstance(headings[0], Tag)
                    and not headings[0].select("a[href]")
                    and headings[0].get_text(" ", strip=True)
                ):
                    return headings[0], source_group_id, source_canonical, True
        identities = {(group_id, canonical) for _, group_id, canonical in matches}
        if len(identities) != 1:
            raise UnsupportedLayoutError("supported group canonical link is missing or ambiguous")
        group_id, canonical = identities.pop()
        link = next(item for item, item_id, _ in matches if item_id == group_id)
        return link, group_id, canonical, False

    @classmethod
    def _post_anchors(cls, soup: BeautifulSoup, source_url: str) -> list[tuple[Tag, str, str, str]]:
        values: list[tuple[Tag, str, str, str]] = []
        for article in soup.select("[role='article']"):
            if not isinstance(article, Tag):
                continue
            link_match: tuple[str, str, str] | None = None
            for link in article.select("a[href]"):
                if not isinstance(link, Tag):
                    continue
                absolute = urljoin(source_url, cls._required_href(link))
                parts = urlsplit(absolute)
                if parse_qs(parts.query).get("comment_id"):
                    continue
                match = _POST_PATH.fullmatch(parts.path.rstrip("/"))
                if match:
                    canonical = cls._canonical_url(source_url, absolute)
                    link_match = (match.group(1), match.group(2), canonical)
                    break
            if link_match is None:
                continue
            parent_article = article.find_parent("article", attrs={"role": "article"})
            if parent_article is not None:
                continue
            values.append((article, *link_match))
        return values

    @classmethod
    def _has_post_anchor(cls, soup: BeautifulSoup) -> bool:
        return any(
            isinstance(link, Tag)
            and _POST_PATH.fullmatch(urlsplit(str(link.get("href", ""))).path.rstrip("/"))
            for link in soup.select("a[href]")
        )

    @classmethod
    def _comment_id(cls, tag: Tag, group_id: str, post_id: str) -> str:
        structured = tag.get("data-commentid")
        structured_id = structured.strip() if isinstance(structured, str) else None
        linked_ids: set[str] = set()
        for link in tag.select("a[href]"):
            if not isinstance(link, Tag):
                continue
            if link.find_parent(attrs={"data-commentid": True}) is not tag:
                continue
            parts = urlsplit(cls._required_href(link))
            match = _POST_PATH.fullmatch(parts.path.rstrip("/"))
            values = parse_qs(parts.query).get("comment_id", [])
            if match and match.groups() == (group_id, post_id):
                linked_ids.update(value.strip() for value in values if value.strip())
        candidates = linked_ids | ({structured_id} if structured_id else set())
        if len(candidates) != 1:
            raise UnsupportedLayoutError("Comment identifier is missing or ambiguous")
        return candidates.pop()

    @staticmethod
    def _top_level_comments(post_tag: Tag) -> list[Tag]:
        comments: list[Tag] = []
        for tag in post_tag.select("[role='article'][data-commentid]"):
            if not isinstance(tag, Tag):
                continue
            depth = tag.get("data-depth")
            if isinstance(depth, str) and depth.strip() not in {"", "0"}:
                continue
            if tag.find_parent(attrs={"data-commentid": True}) is not None:
                continue
            comments.append(tag)
        return comments

    @classmethod
    def _author(cls, tag: Tag) -> tuple[str | None, str | None]:
        for link in tag.select("a[href]"):
            if not isinstance(link, Tag):
                continue
            href = cls._required_href(link)
            parts = urlsplit(href)
            path = parts.path.strip("/")
            identifier: str | None = None
            if path == "profile.php":
                identifier = parse_qs(parts.query).get("id", [None])[0]
            elif path and "/" not in path and path not in {"groups", "media"}:
                identifier = path
            if identifier and _INTEGER.fullmatch(identifier):
                name = link.get_text(" ", strip=True) or None
                return identifier, name
        return None, None

    @classmethod
    def _media(
        cls,
        owner: Tag,
        source_url: str,
        *,
        owner_comment: Tag | None,
    ) -> list[MediaReference]:
        values: list[MediaReference] = []
        seen: set[tuple[str, str]] = set()
        for media in owner.select("img[src], video[src], video source[src]"):
            if not isinstance(media, Tag):
                continue
            comment_ancestor = media.find_parent(attrs={"data-commentid": True})
            if owner_comment is None and comment_ancestor is not None:
                continue
            if owner_comment is not None and comment_ancestor is not owner_comment:
                continue
            media_type = "image" if media.name == "img" else "video"
            source = urljoin(source_url, cls._required_attr(media, "src"))
            key = (media_type, source)
            if key in seen:
                continue
            seen.add(key)
            alt = media.get("alt")
            values.append(
                MediaReference(
                    media_type=media_type,
                    source_url=source,
                    alt_text=alt.strip() if isinstance(alt, str) and alt.strip() else None,
                )
            )
        return values

    @classmethod
    def _time(cls, tag: Tag) -> datetime | None:
        time_tag = tag.select_one("time[datetime]")
        if isinstance(time_tag, Tag):
            raw = cls._required_attr(time_tag, "datetime")
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as error:
                raise UnsupportedLayoutError("invalid rendered timestamp") from error
            return cls._aware(value, "rendered timestamp")
        unix_tag = tag.select_one("abbr[data-utime]")
        if isinstance(unix_tag, Tag):
            try:
                return datetime.fromtimestamp(
                    int(cls._required_attr(unix_tag, "data-utime")), tz=UTC
                )
            except (OverflowError, ValueError) as error:
                raise UnsupportedLayoutError("invalid rendered Unix timestamp") from error
        return None

    @staticmethod
    def _optional_text(tag: Tag | BeautifulSoup, selector: str) -> str | None:
        value = tag.select_one(selector)
        if not isinstance(value, Tag):
            return None
        text = value.get_text(" ", strip=True)
        return text or None

    @classmethod
    def _optional_count(cls, tag: Tag | BeautifulSoup, selector: str) -> int | None:
        value = cls._optional_text(tag, selector)
        if value is None:
            return None
        match = _INTEGER.search(value.replace(",", ""))
        if match is None:
            raise UnsupportedLayoutError(f"invalid rendered count: {selector}")
        return int(match.group())

    @classmethod
    def _canonical_url(cls, source_url: str, href: str) -> str:
        source = urlsplit(source_url)
        absolute = urlsplit(urljoin(source_url, href))
        if source.hostname != absolute.hostname:
            raise UnsupportedLayoutError("canonical link host does not match capture source")
        path = absolute.path.rstrip("/") or "/"
        return urlunsplit((absolute.scheme, absolute.netloc, path, "", ""))

    @staticmethod
    def _required_href(tag: Tag) -> str:
        return AppGroupExtractionAdapter._required_attr(tag, "href")

    @staticmethod
    def _required_attr(tag: Tag, name: str) -> str:
        value = tag.get(name)
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedLayoutError(f"required rendered attribute is missing: {name}")
        return value.strip()

    @staticmethod
    def _aware(value: datetime, name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        return value.astimezone(UTC)

    @classmethod
    def _evidence(
        cls,
        data: dict[str, Any],
        *,
        source_url: str,
        capture_id: str,
        raw_sha256: str,
        session_class: SessionClass,
        observed_at: datetime,
        paths: dict[str, tuple[str, str | None]],
        nullable: frozenset[str],
    ) -> dict[str, Any]:
        field_provenance = {
            name: FieldProvenance(
                source_path=path,
                confidence=1.0,
                transformation=transformation,
            )
            for name, value in data.items()
            if value is not None
            for path, transformation in [paths[name]]
        }
        null_reasons = {name: NullReason.NOT_PRESENT for name in nullable if data.get(name) is None}
        return {
            **data,
            "schema_version": "1.0",
            "adapter_name": cls.adapter_name,
            "adapter_version": cls.adapter_version,
            "parser_version": cls.parser_version,
            "collected_at": observed_at,
            "raw_capture_id": capture_id,
            "raw_sha256": raw_sha256,
            "source_url": source_url,
            "session_class": session_class,
            "visibility_context": "operator_visible_group",
            "field_provenance": field_provenance,
            "null_reasons": null_reasons,
            "collection_health": CollectionHealth.OBSERVED,
            "availability": CollectionHealth.OBSERVED,
        }

    @staticmethod
    def _post_paths() -> dict[str, tuple[str, str | None]]:
        return {
            "post_id": (
                "css=article[role=article] a[href*='/posts/']@href",
                "canonical_link_segment",
            ),
            "group_id": (
                "css=article[role=article] a[href*='/posts/']@href",
                "canonical_link_segment",
            ),
            "canonical_url": ("css=article[role=article] a[href*='/posts/']@href", "canonical_url"),
            "author_id": ("css=article[role=article] a[href]@href", "profile_link_segment"),
            "author_name": ("css=article[role=article] a[href]::text", None),
            "published_at": ("css=article[role=article] time@datetime", "iso8601"),
            "observed_at": ("capture=collected_at", None),
            "text": ("css=[data-ad-preview=message]::text", None),
            "post_type": ("derived=media_presence", "media_classification"),
            "media": ("css=article[role=article] img,video", "media_metadata"),
            "reactions": ("derived=visible_reaction_controls", "empty_when_absent"),
            "comments_count": ("derived=visible_top_level_comments", "count"),
            "shares_count": ("derived=visible_share_controls", "zero_when_absent"),
        }

    @staticmethod
    def _comment_paths() -> dict[str, tuple[str, str | None]]:
        return {
            "comment_id": ("css=[role=article][data-commentid]", "structured_identifier"),
            "post_id": (
                "css=[role=article][data-commentid] a[href*='/posts/']",
                "canonical_link_segment",
            ),
            "group_id": (
                "css=[role=article][data-commentid] a[href*='/groups/']",
                "canonical_link_segment",
            ),
            "parent_comment_id": ("derived=top_level_filter", "constant_null"),
            "author_id": (
                "css=[role=article][data-commentid] a[href]@href",
                "profile_link_segment",
            ),
            "author_name": ("css=[role=article][data-commentid] a[href]::text", None),
            "published_at": ("css=[role=article][data-commentid] time@datetime", "iso8601"),
            "observed_at": ("capture=collected_at", None),
            "text": ("css=[data-ad-preview=comment]::text", None),
            "media": ("css=[role=article][data-commentid] img,video", "media_metadata"),
            "reactions": ("derived=visible_reaction_controls", "empty_when_absent"),
        }

    @staticmethod
    def _add_unique(
        values: dict[str, _Record],
        identifier: str,
        record: _Record,
        label: str,
    ) -> None:
        previous = values.get(identifier)
        if previous is not None:
            old = json.dumps(previous.model_dump(mode="json"), sort_keys=True)
            new = json.dumps(record.model_dump(mode="json"), sort_keys=True)
            if old != new:
                raise UnsupportedLayoutError(
                    f"conflicting duplicate {label} identity: {identifier}"
                )
        values[identifier] = record
