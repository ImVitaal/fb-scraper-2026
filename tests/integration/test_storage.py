from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.contracts.models import (
    CollectionHealth,
    CommentRecord,
    GroupRecord,
    JobState,
    NullReason,
    PostRecord,
    SessionClass,
)
from app.storage.database import Database
from app.storage.repositories import (
    CanonicalRepository,
    InvalidStateTransition,
    JobRepository,
    RawCaptureMetadataRepository,
)


def group_record(*, observed_at: datetime, member_count: int) -> GroupRecord:
    return GroupRecord(
        adapter_name="fixture",
        adapter_version="1.0.0",
        parser_version="1.0.0",
        collected_at=observed_at,
        raw_capture_id=f"capture-{member_count}",
        raw_sha256=f"{member_count:064x}",
        source_url="https://example.test/groups/123",
        session_class=SessionClass.FIXTURE,
        visibility_context="fixture",
        field_provenance={"group_id": {"source_path": "$.id", "confidence": 1.0}},
        null_reasons={"description": NullReason.NOT_PRESENT},
        collection_health=CollectionHealth.OBSERVED,
        group_id="123",
        canonical_url="https://example.test/groups/123",
        name="Example Group",
        privacy="private",
        membership_state="member",
        description=None,
        member_count=member_count,
        observed_at=observed_at,
        availability=CollectionHealth.OBSERVED,
    )


def post_record(*, observed_at: datetime) -> PostRecord:
    return PostRecord(
        adapter_name="fixture",
        adapter_version="1.0.0",
        parser_version="1.0.0",
        collected_at=observed_at,
        raw_capture_id="capture-post",
        raw_sha256="b" * 64,
        source_url="https://example.test/groups/123/posts/post-1",
        session_class=SessionClass.FIXTURE,
        visibility_context="fixture",
        field_provenance={"post_id": {"source_path": "$.id", "confidence": 1.0}},
        null_reasons={},
        collection_health=CollectionHealth.OBSERVED,
        post_id="post-1",
        group_id="123",
        canonical_url="https://example.test/groups/123/posts/post-1",
        author_id="author-1",
        author_name="Example Author",
        published_at=observed_at,
        observed_at=observed_at,
        text="Fixture post",
        post_type="text",
        media=[],
        reactions={"like": 3},
        comments_count=1,
        shares_count=2,
        availability=CollectionHealth.OBSERVED,
    )


def comment_record(*, observed_at: datetime) -> CommentRecord:
    return CommentRecord(
        adapter_name="fixture",
        adapter_version="1.0.0",
        parser_version="1.0.0",
        collected_at=observed_at,
        raw_capture_id="capture-comment",
        raw_sha256="c" * 64,
        source_url="https://example.test/groups/123/posts/post-1?comment_id=comment-1",
        session_class=SessionClass.FIXTURE,
        visibility_context="fixture",
        field_provenance={"comment_id": {"source_path": "$.id", "confidence": 1.0}},
        null_reasons={},
        collection_health=CollectionHealth.OBSERVED,
        comment_id="comment-1",
        post_id="post-1",
        group_id="123",
        parent_comment_id=None,
        author_id="author-2",
        author_name="Example Commenter",
        published_at=observed_at,
        observed_at=observed_at,
        text="Fixture comment",
        media=[],
        reactions={"like": 1},
        availability=CollectionHealth.OBSERVED,
    )


def test_migrations_round_trip_and_remain_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "scanner.sqlite3"

    with Database(database_path) as database:
        first = database.migrate()
        second = database.migrate()
        tables = database.table_names()

    with Database(database_path) as reopened:
        third = reopened.migrate()
        versions = reopened.applied_versions()
        foreign_keys = reopened.connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert first == [1]
    assert second == []
    assert third == []
    assert versions == [1]
    assert foreign_keys == 1
    assert {
        "schema_versions",
        "session_profiles",
        "discovery_campaigns",
        "jobs",
        "raw_captures",
        "pagination_checkpoints",
        "groups",
        "posts",
        "comments",
        "counter_observations",
        "export_manifests",
        "cleanup_receipts",
    } <= tables


def test_packaged_migrations_match_repository_migrations() -> None:
    repository_migration = Path("migrations/001_initial.sql")
    packaged_migration = Path("src/app/storage/migrations/001_initial.sql")

    assert packaged_migration.read_bytes() == repository_migration.read_bytes()


def test_canonical_repository_keeps_counter_observation_history(tmp_path: Path) -> None:
    first_time = datetime(2026, 7, 29, 12, tzinfo=UTC)
    second_time = datetime(2026, 7, 29, 13, tzinfo=UTC)

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        captures = RawCaptureMetadataRepository(database.connection)
        records = CanonicalRepository(database.connection)
        for count, observed_at in ((10, first_time), (12, second_time)):
            record = group_record(observed_at=observed_at, member_count=count)
            captures.add(
                capture_id=record.raw_capture_id,
                sha256=record.raw_sha256,
                source_url=str(record.source_url),
                collected_at=record.collected_at,
            )
            records.save_group(record)

        current = records.get_group("123")
        observations = records.counter_observations("group", "123", "member_count")

    assert current is not None
    assert current.member_count == 12
    assert [(item.observed_at, item.value) for item in observations] == [
        (first_time, 10),
        (second_time, 12),
    ]


def test_canonical_repository_persists_related_posts_and_comments(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 29, 14, tzinfo=UTC)
    group = group_record(observed_at=observed_at, member_count=12)
    post = post_record(observed_at=observed_at)
    comment = comment_record(observed_at=observed_at)

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        captures = RawCaptureMetadataRepository(database.connection)
        records = CanonicalRepository(database.connection)
        for record in (group, post, comment):
            captures.add(
                capture_id=record.raw_capture_id,
                sha256=record.raw_sha256,
                source_url=str(record.source_url),
                collected_at=record.collected_at,
            )

        records.save_group(group)
        records.save_post(post)
        records.save_comment(comment)

        stored_post = records.get_post("post-1")
        stored_comment = records.get_comment("comment-1")
        post_reactions = records.counter_observations("post", "post-1", "reaction:like")
        comment_reactions = records.counter_observations("comment", "comment-1", "reaction:like")

    assert stored_post == post
    assert stored_comment == comment
    assert [item.value for item in post_reactions] == [3]
    assert [item.value for item in comment_reactions] == [1]


def test_job_repository_enforces_state_transitions(tmp_path: Path) -> None:
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        jobs = JobRepository(database.connection)
        jobs.create("job-1")
        jobs.transition("job-1", JobState.RUNNING)
        jobs.transition("job-1", JobState.INTERRUPTED)
        jobs.transition("job-1", JobState.RUNNING)
        jobs.transition("job-1", JobState.SUCCEEDED)

        with pytest.raises(InvalidStateTransition):
            jobs.transition("job-1", JobState.RUNNING)

        assert jobs.get_state("job-1") is JobState.SUCCEEDED
