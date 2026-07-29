"""Strict, versioned contracts for Phase 1 normalized data."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class WorkItemState(StrEnum):
    """Allowed implementation work-item states."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETE = "complete"


class JobState(StrEnum):
    """Allowed durable job states."""

    PLANNED = "planned"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class CollectionHealth(StrEnum):
    """Allowed collection and availability classifications."""

    OBSERVED = "observed"
    UNCHANGED = "unchanged"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    ACCESS_LIMITED = "access_limited"
    MEMBERSHIP_REQUIRED = "membership_required"
    LOGIN_REQUIRED = "login_required"
    SESSION_INVALID = "session_invalid"
    SESSION_EXPIRED = "session_expired"
    SESSION_CHALLENGED = "session_challenged"
    SESSION_RESTRICTED = "session_restricted"
    TEMPORARILY_BLOCKED = "temporarily_blocked"
    RATE_LIMITED = "rate_limited"
    PARSER_DRIFT = "parser_drift"
    NETWORK_FAILED = "network_failed"


class SessionClass(StrEnum):
    """Non-secret source classification for a collection session."""

    IMPORTED = "imported"
    GUIDED_LOGIN = "guided_login"
    FIXTURE = "fixture"
    REPLAY = "replay"


class NullReason(StrEnum):
    """Structured reasons for absent field values."""

    NOT_OBSERVED = "not_observed"
    NOT_PRESENT = "not_present"
    UNSUPPORTED = "unsupported"
    REDACTED = "redacted"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"


class FieldProvenance(BaseModel):
    """Evidence describing where one normalized field came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_path: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    transformation: str | None = None


class MediaReference(BaseModel):
    """Media metadata without downloaded media bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    media_type: str = Field(min_length=1)
    source_url: HttpUrl
    alt_text: str | None = None


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        message = "datetime must be timezone-aware"
        raise ValueError(message)
    return value


class EvidenceFields(BaseModel):
    """Evidence fields included with every normalized record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    adapter_name: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    collected_at: datetime
    raw_capture_id: str = Field(min_length=1)
    raw_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    source_url: HttpUrl
    session_class: SessionClass
    visibility_context: str = Field(min_length=1)
    field_provenance: dict[str, FieldProvenance]
    null_reasons: dict[str, NullReason]
    collection_health: CollectionHealth

    _validate_collected_at = field_validator("collected_at")(_require_aware)

    @field_validator("raw_sha256")
    @classmethod
    def normalize_sha256(cls, value: str) -> str:
        """Store hashes in one canonical representation."""
        return value.lower()


class CanonicalRecord(EvidenceFields):
    """Common validation for normalized records."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def require_null_reasons(self) -> Self:
        """Require an explicit reason for every absent supported field."""
        missing = sorted(
            field_name
            for field_name in self.nullable_fields
            if getattr(self, field_name) is None and field_name not in self.null_reasons
        )
        if missing:
            message = f"null reason required for: {', '.join(missing)}"
            raise ValueError(message)
        return self


class GroupRecord(CanonicalRecord):
    """Version 1 normalized private-Group record."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset({"description", "member_count"})

    group_id: str = Field(min_length=1)
    canonical_url: HttpUrl
    name: str = Field(min_length=1)
    privacy: str = Field(min_length=1)
    membership_state: str = Field(min_length=1)
    description: str | None
    member_count: int | None = Field(default=None, ge=0)
    observed_at: datetime
    availability: CollectionHealth

    _validate_observed_at = field_validator("observed_at")(_require_aware)


class PostRecord(CanonicalRecord):
    """Version 1 normalized private-Group post record."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"author_id", "author_name", "published_at", "text"}
    )

    post_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    canonical_url: HttpUrl
    author_id: str | None
    author_name: str | None
    published_at: datetime | None
    observed_at: datetime
    text: str | None
    post_type: str = Field(min_length=1)
    media: list[MediaReference]
    reactions: dict[str, int]
    comments_count: int = Field(ge=0)
    shares_count: int = Field(ge=0)
    availability: CollectionHealth

    _validate_post_times = field_validator("published_at", "observed_at")(
        lambda value: _require_aware(value) if value is not None else value
    )

    @field_validator("reactions")
    @classmethod
    def validate_reaction_counts(cls, value: dict[str, int]) -> dict[str, int]:
        """Reject negative reaction counters."""
        if any(count < 0 for count in value.values()):
            message = "reaction counts must be non-negative"
            raise ValueError(message)
        return value


class CommentRecord(CanonicalRecord):
    """Version 1 normalized top-level Comment record."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"author_id", "author_name", "published_at", "text"}
    )

    comment_id: str = Field(min_length=1)
    post_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    parent_comment_id: None = None
    author_id: str | None
    author_name: str | None
    published_at: datetime | None
    observed_at: datetime
    text: str | None
    media: list[MediaReference]
    reactions: dict[str, int]
    availability: CollectionHealth

    _validate_comment_times = field_validator("published_at", "observed_at")(
        lambda value: _require_aware(value) if value is not None else value
    )

    @model_validator(mode="before")
    @classmethod
    def enforce_top_level_only(cls, values: object) -> object:
        """Reject reply records during Phase 1."""
        if isinstance(values, dict) and values.get("parent_comment_id") is not None:
            message = "Phase 1 supports top-level comments only"
            raise ValueError(message)
        return values

    @field_validator("reactions")
    @classmethod
    def validate_reaction_counts(cls, value: dict[str, int]) -> dict[str, int]:
        """Reject negative reaction counters."""
        if any(count < 0 for count in value.values()):
            message = "reaction counts must be non-negative"
            raise ValueError(message)
        return value


class CounterObservation(BaseModel):
    """One immutable observation of a changing counter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    observed_at: datetime
    value: int = Field(ge=0)
    raw_capture_id: str = Field(min_length=1)

    _validate_observed_at = field_validator("observed_at")(_require_aware)
