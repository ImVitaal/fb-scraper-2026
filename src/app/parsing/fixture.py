"""Parser for synthetic Milestone 1A raw-capture fixtures."""

from __future__ import annotations

import json
from typing import Any, cast

from app.contracts.models import (
    CollectionHealth,
    CommentRecord,
    FieldProvenance,
    GroupRecord,
    PostRecord,
    SessionClass,
)


class FixtureParseError(ValueError):
    """Raised when a synthetic raw fixture does not match the supported layout."""


class FixtureCaptureParser:
    """Map one fixture capture into versioned Group, Post, and Comment records."""

    adapter_name = "fixture"
    adapter_version = "1.0"
    parser_version = "1.0"

    def parse(
        self,
        raw_bytes: bytes,
        *,
        capture_id: str,
        raw_sha256: str,
    ) -> tuple[GroupRecord, list[PostRecord], list[CommentRecord]]:
        """Parse a complete synthetic Group capture after raw persistence."""
        try:
            fixture = json.loads(raw_bytes)
        except json.JSONDecodeError as error:
            raise FixtureParseError("fixture is not valid JSON") from error
        if not isinstance(fixture, dict):
            raise FixtureParseError("fixture root must be an object")
        expected_keys = {"fixture_version", "captured_at", "source_url", "group", "posts"}
        if set(fixture) != expected_keys:
            raise FixtureParseError("fixture root has an unsupported layout")
        if fixture.get("fixture_version") != "1.0":
            raise FixtureParseError("fixture version is unsupported")
        try:
            source_url = str(fixture["source_url"])
            collected_at = fixture["captured_at"]
            group_data = self._object(fixture["group"], "group")
            posts_data = self._objects(fixture["posts"], "posts")
        except KeyError as error:
            raise FixtureParseError(f"fixture missing field: {error.args[0]}") from error

        group = GroupRecord.model_validate(
            self._with_evidence(
                group_data, "$.group", source_url, collected_at, capture_id, raw_sha256
            )
        )
        posts: list[PostRecord] = []
        comments: list[CommentRecord] = []
        for index, post_data in enumerate(posts_data):
            post = PostRecord.model_validate(
                self._with_evidence(
                    self._without(post_data, "comments"),
                    f"$.posts[{index}]",
                    source_url,
                    collected_at,
                    capture_id,
                    raw_sha256,
                )
            )
            if post.group_id != group.group_id:
                raise FixtureParseError("post group_id does not match fixture group")
            posts.append(post)
            for comment_index, comment_data in enumerate(
                self._objects(post_data.get("comments", []), "comments")
            ):
                comment = CommentRecord.model_validate(
                    self._with_evidence(
                        comment_data,
                        f"$.posts[{index}].comments[{comment_index}]",
                        source_url,
                        collected_at,
                        capture_id,
                        raw_sha256,
                    )
                )
                if comment.group_id != group.group_id or comment.post_id != post.post_id:
                    raise FixtureParseError("comment parent identifiers do not match fixture post")
                comments.append(comment)
        return group, posts, comments

    @staticmethod
    def _object(value: object, field_name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise FixtureParseError(f"fixture {field_name} must be an object")
        return cast(dict[str, Any], value)

    @classmethod
    def _objects(cls, value: object, field_name: str) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            raise FixtureParseError(f"fixture {field_name} must be an array")
        return [cls._object(item, field_name) for item in value]

    @staticmethod
    def _without(value: dict[str, Any], *keys: str) -> dict[str, Any]:
        return {key: item for key, item in value.items() if key not in keys}

    def _with_evidence(
        self,
        data: dict[str, Any],
        source_path: str,
        source_url: str,
        collected_at: object,
        capture_id: str,
        raw_sha256: str,
    ) -> dict[str, Any]:
        value = dict(data)
        value.update(
            {
                "schema_version": "1.0",
                "adapter_name": self.adapter_name,
                "adapter_version": self.adapter_version,
                "parser_version": self.parser_version,
                "collected_at": collected_at,
                "raw_capture_id": capture_id,
                "raw_sha256": raw_sha256,
                "source_url": source_url,
                "session_class": SessionClass.FIXTURE,
                "visibility_context": "synthetic_fixture",
                "field_provenance": self._provenance(value, source_path),
                "null_reasons": {},
                "collection_health": CollectionHealth.OBSERVED,
                "availability": CollectionHealth.OBSERVED,
            }
        )
        return value

    @staticmethod
    def _provenance(data: dict[str, Any], source_path: str) -> dict[str, FieldProvenance]:
        return {
            name: FieldProvenance(source_path=f"{source_path}.{name}", confidence=1.0)
            for name, value in data.items()
            if value is not None
        }
