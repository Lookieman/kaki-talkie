# v1.0 | 13-Sep-2026 | Open the SQLite database, apply pragmas per connection and migrate.
"""Own the SQLite file: create it privately, connect safely and migrate it.

Every connection gets the same pragmas (ADR-0007). SQLite scopes
`foreign_keys`, `busy_timeout` and `synchronous` to the connection, so they
are applied each time one opens rather than once at startup. Connections are
short-lived, one per operation, which keeps them off shared threads: FastAPI
runs sync routes in a worker pool and the turn pipeline in another thread.

Migrations run at backend start, each in its own transaction that also sets
`PRAGMA user_version`, so a failed migration leaves the previous version
intact. A database whose version is newer than this build refuses to open.
The design assumes one backend process writes the file.
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from kaki_backend.persistence.migrations import Migration, check_sequence, load_migrations

BUSY_TIMEOUT_MS = 5000
CONNECTION_PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA foreign_keys = ON",
    f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}",
    "PRAGMA synchronous = NORMAL",
)
DATABASE_FILE_MODE = 0o600
DATABASE_DIRECTORY_MODE = 0o700


class DatabaseError(RuntimeError):
    """Signal a database that this build cannot safely open."""


class Database:
    """Provide configured connections to one SQLite file and keep its schema current."""

    def __init__(self, path: str | Path, migrations: tuple[Migration, ...] | None = None) -> None:
        """Bind to a file path without touching the filesystem.

        `migrations` defaults to the packaged set; tests may pass their own.
        Raises ValueError when the migration numbering is not contiguous.
        """
        self.path = Path(path)
        self._migrations = load_migrations() if migrations is None else migrations
        check_sequence(self._migrations)

    @classmethod
    def open(cls, path: str | Path) -> "Database":
        """Create the file if absent, apply pending migrations and return the database.

        Side effects: may create the parent directory (mode 0700) and the file
        (mode 0600). Raises DatabaseError for a newer schema, and
        `sqlite3.Error` or OSError when the file cannot be used.
        """
        database = cls(path)
        database.create_file()
        database.migrate()
        return database

    @property
    def latest_version(self) -> int:
        """Return the schema version this build's migrations produce."""
        return self._migrations[-1].version if self._migrations else 0

    def create_file(self) -> None:
        """Create the database file owner-only; an existing file keeps its mode."""
        self.path.parent.mkdir(mode=DATABASE_DIRECTORY_MODE, parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, DATABASE_FILE_MODE)
        os.close(descriptor)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a new autocommit connection with the ADR-0007 pragmas applied.

        Callers open transactions explicitly (`BEGIN IMMEDIATE` ... `COMMIT`).
        The connection closes when the block exits.
        """
        connection = sqlite3.connect(
            self.path, isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000,
        )
        try:
            connection.row_factory = sqlite3.Row
            for pragma in CONNECTION_PRAGMAS:
                connection.execute(pragma)
            yield connection
        finally:
            connection.close()

    def schema_version(self) -> int:
        """Return the file's current `PRAGMA user_version`."""
        with self.connect() as connection:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def migrate(self) -> int:
        """Apply every migration newer than the file's version; return the final version.

        Raises DatabaseError when the file is newer than this build. A failing
        migration is rolled back and its `sqlite3.Error` propagates.
        """
        with self.connect() as connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current > self.latest_version:
                raise DatabaseError(
                    f"SQLite database {self.path} is at schema version {current}, newer than "
                    f"this build supports ({self.latest_version}). Use a current checkout."
                )
            for migration in self._migrations:
                if migration.version <= current:
                    continue
                try:
                    connection.executescript(
                        f"BEGIN IMMEDIATE;\n{migration.sql}\n"
                        f"PRAGMA user_version = {migration.version};\nCOMMIT;"
                    )
                except sqlite3.Error:
                    if connection.in_transaction:
                        connection.execute("ROLLBACK")
                    raise
            return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def ready(self) -> bool:
        """Report whether the file answers a query at this build's schema version."""
        try:
            with self.connect() as connection:
                connection.execute("SELECT 1").fetchone()
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        except (sqlite3.Error, OSError):
            return False
        return version == self.latest_version
