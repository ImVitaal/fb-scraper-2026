"""SQLite connection management and ordered migration execution."""

from __future__ import annotations

import re
import sqlite3
from hashlib import sha256
from pathlib import Path
from types import TracebackType

MIGRATION_PATTERN = re.compile(r"^(?P<version>\d{3})_[a-z0-9_]+\.sql$")


def _migration_checksum(content: bytes) -> str:
    normalized = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


class MigrationError(RuntimeError):
    """Raised when migration files or the database version are invalid."""


class Database:
    """Own one SQLite connection with required integrity settings."""

    def __init__(self, path: Path, migrations_path: Path | None = None) -> None:
        self.path = path
        self.migrations_path = migrations_path or self._default_migrations_path()
        path.parent.mkdir(parents=True, exist_ok=True)
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
        migration_files = self._migration_files()
        self._ensure_version_table()
        applied = self._validate_applied_migrations(migration_files)
        completed: list[int] = []

        for version, migration_path in migration_files:
            if version in applied:
                continue
            migration_bytes = migration_path.read_bytes()
            sql = migration_bytes.decode("utf-8")
            checksum = _migration_checksum(migration_bytes)
            applied_at = self.connection.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
            ).fetchone()[0]
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{sql}\n"
                "INSERT INTO schema_versions(version, name, checksum, applied_at) "
                f"VALUES ({version}, {self._quote(migration_path.name)}, "
                f"{self._quote(checksum)}, {self._quote(applied_at)});\n"
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
                checksum TEXT,
                applied_at TEXT NOT NULL
            )
            """
        )
        columns = {
            str(row["name"])
            for row in self.connection.execute("PRAGMA table_info(schema_versions)")
        }
        if "checksum" not in columns:
            self.connection.execute("ALTER TABLE schema_versions ADD COLUMN checksum TEXT")
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
        if versions and versions != list(range(1, versions[-1] + 1)):
            message = "migration versions must be contiguous from 001"
            raise MigrationError(message)
        return migrations

    def _validate_applied_migrations(
        self,
        migration_files: list[tuple[int, Path]],
    ) -> set[int]:
        available = {version: path for version, path in migration_files}
        rows = self.connection.execute(
            "SELECT version, name, checksum FROM schema_versions ORDER BY version"
        ).fetchall()
        applied: set[int] = set()

        for row in rows:
            version = int(row["version"])
            migration_path = available.get(version)
            if migration_path is None:
                message = f"applied migration {version:03d} is missing"
                raise MigrationError(message)
            if row["name"] != migration_path.name:
                message = f"applied migration {version:03d} name mismatch"
                raise MigrationError(message)

            checksum = _migration_checksum(migration_path.read_bytes())
            stored_checksum = row["checksum"]
            if stored_checksum is None:
                self.connection.execute(
                    "UPDATE schema_versions SET checksum = ? WHERE version = ?",
                    (checksum, version),
                )
                self.connection.commit()
            elif stored_checksum != checksum:
                message = f"applied migration {version:03d} checksum mismatch"
                raise MigrationError(message)
            applied.add(version)

        return applied

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def _default_migrations_path() -> Path:
        return Path(__file__).with_name("migrations")
