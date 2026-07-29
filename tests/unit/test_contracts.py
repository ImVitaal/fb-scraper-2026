from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.contracts.models import (
    CollectionHealth,
    CommentRecord,
    EvidenceFields,
    GroupRecord,
    JobState,
    NullReason,
    SessionClass,
    WorkItemState,
)


def evidence() -> EvidenceFields:
    return EvidenceFields(
        adapter_name="fixture",
        adapter_version="1.0.0",
        parser_version="1.0.0",
        collected_at=datetime(2026, 7, 29, tzinfo=UTC),
        raw_capture_id="capture-1",
        raw_sha256="A" * 64,
        source_url="https://example.test/groups/123",
        session_class=SessionClass.FIXTURE,
        visibility_context="fixture",
        field_provenance={"group_id": {"source_path": "$.id", "confidence": 1.0}},
        null_reasons={
            "description": NullReason.NOT_PRESENT,
            "member_count": NullReason.NOT_OBSERVED,
        },
        collection_health=CollectionHealth.OBSERVED,
    )


def test_state_vocabularies_match_the_phase_one_plan() -> None:
    assert {state.value for state in WorkItemState} == {
        "planned",
        "in_progress",
        "blocked",
        "review",
        "complete",
    }
    assert {state.value for state in JobState} == {
        "planned",
        "running",
        "partial",
        "succeeded",
        "failed",
        "interrupted",
        "cancelled",
    }
    assert {state.value for state in CollectionHealth} == {
        "observed",
        "unchanged",
        "partial",
        "unavailable",
        "access_limited",
        "membership_required",
        "login_required",
        "session_invalid",
        "session_expired",
        "session_challenged",
        "session_restricted",
        "temporarily_blocked",
        "rate_limited",
        "parser_drift",
        "network_failed",
    }


def test_group_contract_normalizes_hash_and_requires_aware_times() -> None:
    record = GroupRecord(
        **evidence().model_dump(),
        group_id="123",
        canonical_url="https://example.test/groups/123",
        name="Example Group",
        privacy="private",
        membership_state="member",
        description=None,
        member_count=None,
        observed_at=datetime(2026, 7, 29, tzinfo=UTC),
        availability=CollectionHealth.OBSERVED,
    )

    assert record.raw_sha256 == "a" * 64

    with pytest.raises(ValidationError, match="timezone-aware"):
        GroupRecord(
            **evidence().model_dump(exclude={"observed_at"}),
            group_id="123",
            canonical_url="https://example.test/groups/123",
            name="Example Group",
            privacy="private",
            membership_state="member",
            description=None,
            member_count=None,
            observed_at=datetime(2026, 7, 29),
            availability=CollectionHealth.OBSERVED,
        )


def test_nullable_fields_require_structured_null_reasons() -> None:
    values = evidence().model_dump()
    values["null_reasons"] = {}

    with pytest.raises(ValidationError, match="null reason"):
        GroupRecord(
            **values,
            group_id="123",
            canonical_url="https://example.test/groups/123",
            name="Example Group",
            privacy="private",
            membership_state="member",
            description=None,
            member_count=None,
            observed_at=datetime(2026, 7, 29, tzinfo=UTC),
            availability=CollectionHealth.OBSERVED,
        )


def test_phase_one_comment_rejects_parent_comment_identifier() -> None:
    values = evidence().model_dump()
    values["null_reasons"] = {
        "author_id": NullReason.NOT_OBSERVED,
        "author_name": NullReason.NOT_OBSERVED,
        "published_at": NullReason.NOT_OBSERVED,
        "text": NullReason.NOT_PRESENT,
    }

    with pytest.raises(ValidationError, match="top-level"):
        CommentRecord.model_validate(
            {
                **values,
                "comment_id": "comment-1",
                "post_id": "post-1",
                "group_id": "123",
                "parent_comment_id": "parent-1",
                "author_id": None,
                "author_name": None,
                "published_at": None,
                "observed_at": datetime(2026, 7, 29, tzinfo=UTC),
                "text": None,
                "media": [],
                "reactions": {},
                "availability": CollectionHealth.OBSERVED,
            }
        )
