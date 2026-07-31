import sqlite3
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
from app.storage.database import Database, MigrationError
from app.storage.repositories import (
    CanonicalIdentityConflict,
    CanonicalRepository,
    CaptureMetadataConflict,
    CounterObservationConflict,
    InvalidStateTransition,
    JobRepository,
    RawCaptureMetadataRepository,
    StaleObservation,
)


def group_record(
    *,
    observed_at: datetime,
    member_count: int,
    group_id: str = "123",
) -> GroupRecord:
    return GroupRecord(
        adapter_name="fixture",
        adapter_version="1.0.0",
        parser_version="1.0.0",
        collected_at=observed_at,
        raw_capture_id=f"capture-{group_id}-{member_count}",
        raw_sha256=f"{member_count:064x}",
        source_url=f"https://example.test/groups/{group_id}",
        session_class=SessionClass.FIXTURE,
        visibility_context="fixture",
        field_provenance={"group_id": {"source_path": "$.id", "confidence": 1.0}},
        null_reasons={"description": NullReason.NOT_PRESENT},
        collection_health=CollectionHealth.OBSERVED,
        group_id=group_id,
        canonical_url=f"https://example.test/groups/{group_id}",
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

    assert first == [1, 2, 3, 4, 5, 6]
    assert second == []
    assert third == []
    assert versions == [1, 2, 3, 4, 5, 6]
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
    repository_migrations = {
        path.name: path.read_bytes() for path in Path("migrations").glob("*.sql")
    }
    packaged_migrations = {
        path.name: path.read_bytes() for path in Path("src/app/storage/migrations").glob("*.sql")
    }

    assert packaged_migrations == repository_migrations


def test_migration_integrity_rejects_modified_applied_file(tmp_path: Path) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    migration = migration_dir / "001_initial.sql"
    migration.write_bytes(Path("migrations/001_initial.sql").read_bytes())

    with Database(tmp_path / "scanner.sqlite3", migration_dir) as database:
        database.migrate()
        migration.write_text(
            migration.read_text(encoding="utf-8") + "\n-- modified\n",
            encoding="utf-8",
        )

        with pytest.raises(MigrationError, match="checksum"):
            database.migrate()


def test_migration_checksum_is_stable_across_line_endings(tmp_path: Path) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    migration = migration_dir / "001_first.sql"
    migration.write_bytes(b"CREATE TABLE first_table(\r\nid INTEGER PRIMARY KEY\r\n);\r\n")

    with Database(tmp_path / "scanner.sqlite3", migration_dir) as database:
        database.migrate()
        migration.write_bytes(b"CREATE TABLE first_table(\nid INTEGER PRIMARY KEY\n);\n")

        assert database.migrate() == []


def test_integrity_migration_upgrades_an_existing_version_one_database(
    tmp_path: Path,
) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "001_initial.sql").write_bytes(Path("migrations/001_initial.sql").read_bytes())
    database_path = tmp_path / "scanner.sqlite3"

    with Database(database_path, migration_dir) as database:
        assert database.migrate() == [1]

    (migration_dir / "002_integrity_guards.sql").write_bytes(
        Path("migrations/002_integrity_guards.sql").read_bytes()
    )
    with Database(database_path, migration_dir) as database:
        assert database.migrate() == [2]
        with pytest.raises(sqlite3.IntegrityError):
            database.connection.execute(
                """
                INSERT INTO session_profiles(
                    profile_id, session_class, health, created_at, inspected_at
                ) VALUES ('profile-1', 'invalid', 'observed', 'TIME', 'TIME')
                """
            )


def test_migrations_reject_version_gaps(tmp_path: Path) -> None:
    migration_dir = tmp_path / "migrations"
    migration_dir.mkdir()
    (migration_dir / "001_first.sql").write_text(
        "CREATE TABLE first_table(id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    (migration_dir / "003_third.sql").write_text(
        "CREATE TABLE third_table(id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )

    with (
        Database(tmp_path / "scanner.sqlite3", migration_dir) as database,
        pytest.raises(MigrationError, match="contiguous"),
    ):
        database.migrate()


def test_sqlite_schema_rejects_invalid_states_and_dangling_capture_ids(
    tmp_path: Path,
) -> None:
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()

        with pytest.raises(sqlite3.IntegrityError):
            database.connection.execute(
                """
                INSERT INTO session_profiles(
                    profile_id, session_class, health, created_at, inspected_at
                ) VALUES ('profile-1', 'invalid', 'observed', 'TIME', 'TIME')
                """
            )

        database.connection.execute(
            """
            INSERT INTO discovery_campaigns(campaign_id, created_at)
            VALUES ('campaign-1', 'TIME')
            """
        )
        database.connection.execute(
            """
            INSERT INTO discovery_queries(
                query_id, campaign_id, keyword, location, created_at
            ) VALUES ('query-1', 'campaign-1', 'keyword', 'location', 'TIME')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            database.connection.execute(
                """
                INSERT INTO candidate_hits(
                    hit_id, query_id, group_id, rank, raw_capture_id, observed_at
                ) VALUES ('hit-1', 'query-1', '123', 1, 'missing-capture', 'TIME')
                """
            )

        database.connection.execute(
            """
            INSERT INTO jobs(job_id, state, created_at, updated_at)
            VALUES ('job-1', 'planned', 'TIME', 'TIME')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            database.connection.execute(
                """
                INSERT INTO tasks(
                    task_id, job_id, idempotency_key, surface, state,
                    created_at, updated_at
                ) VALUES (
                    'task-1', 'job-1', 'key-1', 'group', 'invalid', 'TIME', 'TIME'
                )
                """
            )


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


def test_repository_rejects_stale_records_without_regressing_current_data(
    tmp_path: Path,
) -> None:
    older = group_record(
        observed_at=datetime(2026, 7, 29, 12, tzinfo=UTC),
        member_count=10,
    )
    newer = group_record(
        observed_at=datetime(2026, 7, 29, 13, tzinfo=UTC),
        member_count=12,
    )

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        captures = RawCaptureMetadataRepository(database.connection)
        records = CanonicalRepository(database.connection)
        for record in (older, newer):
            captures.add(
                capture_id=record.raw_capture_id,
                sha256=record.raw_sha256,
                source_url=str(record.source_url),
                collected_at=record.collected_at,
            )

        records.save_group(newer)
        with pytest.raises(StaleObservation):
            records.save_group(older)

        assert records.get_group("123") == newer


def test_repository_rejects_conflicting_counter_observation(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    record = group_record(observed_at=observed_at, member_count=12)

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        captures = RawCaptureMetadataRepository(database.connection)
        captures.add(
            capture_id=record.raw_capture_id,
            sha256=record.raw_sha256,
            source_url=str(record.source_url),
            collected_at=record.collected_at,
        )
        database.connection.execute(
            """
            INSERT INTO counter_observations(
                entity_type, entity_id, metric, observed_at, value, raw_capture_id
            ) VALUES ('group', '123', 'member_count', ?, 99, ?)
            """,
            (observed_at.isoformat(), record.raw_capture_id),
        )
        database.connection.commit()

        records = CanonicalRepository(database.connection)
        with pytest.raises(CounterObservationConflict):
            records.save_group(record)

        assert records.get_group("123") is None


def test_capture_metadata_reports_validation_and_identity_conflicts(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 29, 12, tzinfo=UTC)

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        captures = RawCaptureMetadataRepository(database.connection)

        with pytest.raises(CaptureMetadataConflict, match="sha256"):
            captures.add(
                capture_id="capture-invalid",
                sha256="not-a-hash",
                source_url="https://example.test/capture",
                collected_at=observed_at,
            )

        captures.add(
            capture_id="capture-1",
            sha256="A" * 64,
            source_url="https://example.test/capture",
            collected_at=observed_at,
        )
        with pytest.raises(CaptureMetadataConflict, match="conflict"):
            captures.add(
                capture_id="capture-1",
                sha256="b" * 64,
                source_url="https://example.test/capture",
                collected_at=observed_at,
            )


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


def test_repository_rejects_post_parent_identity_changes(tmp_path: Path) -> None:
    observed_at = datetime(2026, 7, 29, 14, tzinfo=UTC)
    first_group = group_record(observed_at=observed_at, member_count=12)
    second_group = group_record(observed_at=observed_at, member_count=5, group_id="456")
    post = post_record(observed_at=observed_at)
    moved_post = post.model_copy(
        update={
            "group_id": "456",
            "observed_at": datetime(2026, 7, 29, 15, tzinfo=UTC),
        }
    )

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        captures = RawCaptureMetadataRepository(database.connection)
        records = CanonicalRepository(database.connection)
        for record in (first_group, second_group, post):
            captures.add(
                capture_id=record.raw_capture_id,
                sha256=record.raw_sha256,
                source_url=str(record.source_url),
                collected_at=record.collected_at,
            )
        records.save_group(first_group)
        records.save_group(second_group)
        records.save_post(post)

        with pytest.raises(CanonicalIdentityConflict):
            records.save_post(moved_post)

        assert records.get_post("post-1") == post


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
