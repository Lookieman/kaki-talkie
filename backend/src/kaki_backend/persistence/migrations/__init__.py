# v1.0 | 13-Sep-2026 | Load numbered SQL migrations packaged beside this module.
"""Discover the numbered SQL migrations that build the SQLite schema.

Each migration is a file named `NNNN_description.sql`. Its number becomes the
schema version recorded in `PRAGMA user_version` once it has been applied, so
numbers must run contiguously from 0001. A migration is never edited after it
has shipped; a schema change is a new file.
"""

import re
from dataclasses import dataclass
from importlib.resources import files

MIGRATION_FILE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class Migration:
    """One schema step: its version number, file name and SQL text."""

    version: int
    name: str
    sql: str


def check_sequence(migrations: tuple[Migration, ...]) -> None:
    """Raise ValueError unless versions run 1, 2, 3 ... with no gap or repeat."""
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, len(migrations) + 1)):
        raise ValueError(f"Migrations must be numbered contiguously from 0001; found {versions}.")


def load_migrations() -> tuple[Migration, ...]:
    """Return the packaged migrations in version order.

    Raises ValueError when the numbering has a gap or a repeat, so a
    mis-numbered file fails backend startup instead of being skipped.
    """
    found = []
    for entry in files(__name__).iterdir():
        match = MIGRATION_FILE.match(entry.name)
        if match is not None:
            found.append(Migration(int(match.group(1)), entry.name,
                                   entry.read_text(encoding="utf-8")))
    migrations = tuple(sorted(found, key=lambda migration: migration.version))
    check_sequence(migrations)
    return migrations
