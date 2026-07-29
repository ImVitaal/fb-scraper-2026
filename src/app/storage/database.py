"""SQLite connection management and ordered migration execution."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from types import TracebackType

MIGRATION_PATTERN = re.compile(r"^(?P<version>\d{3})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    """Raised when migration files or the database version are invalid."""


class Database:
    """Own one SQLite connection with required integrity settings."""

    def __init__(self, path: Path, migrations_path: Path | None = None) -> None:
        self.path = path
        self.migrations_path = migrations_path or self._default_migrations_path()
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()

    def migrate(self) -> list[int]:
        """Apply every unapplied ordered SQL migration."""
        self._ensure_version_table()
        applied = set(self.applied_versions())
        completed: list[int] = []

        for version, migration_path in self._migration_files():
            if version in applied:
                continue
            sql = migration_path.read_text(encoding="utf-8")
            applied_at = self.connection.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
            ).fetchone()[0]
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{sql}\n"
                "INSERT INTO schema_versions(version, name, applied_at) "
                f"VALUES ({version}, {self._quote(migration_path.name)}, "
                f"{self._quote(applied_at)});\n"
                "COMMIT;"
            )
            try:
                self.connection.executescript(script)
            except sqlite3.Error as error:
                self.connection.rollback()
                message = f"migration {migration_path.name} failed"
                raise MigrationError(message) from error
            completed.append(version)

        return completed

    def applied_versions(self) -> list[int]:
        """Return applied migration versions in order."""
        self._ensure_version_table()
        rows = self.connection.execute(
            "SELECT version FROM schema_versions ORDER BY version"
        ).fetchall()
        return [int(row["version"]) for row in rows]

    def table_names(self) -> set[str]:
        """Return application table names."""
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_version_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_versions (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def _migration_files(self) -> list[tuple[int, Path]]:
        if not self.migrations_path.is_dir():
            message = f"migration directory does not exist: {self.migrations_path}"
            raise MigrationError(message)

        migrations: list[tuple[int, Path]] = []
        for path in sorted(self.migrations_path.glob("*.sql")):
            match = MIGRATION_PATTERN.fullmatch(path.name)
            if match is None:
                message = f"invalid migration filename: {path.name}"
                raise MigrationError(message)
            migrations.append((int(match.group("version")), path))

        versions = [version for version, _ in migrations]
        if len(versions) != len(set(versions)):
            message = "duplicate migration version"
            raise MigrationError(message)
        return migrations

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def _default_migrations_path() -> Path:
        return Path(__file__).with_name("migrations")
