"""Jobcu's local database (SQLite), stored as jobcu.db in the data folder.

Each change to the tables is a numbered migration, applied once, so updating
Jobcu never loses saved data.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from jobcu.paths import ensure_data_dir

DB_FILENAME = "jobcu.db"

MIGRATIONS: list[str] = [
    # 1: AI usage, for the usage meter and monthly limits.
    """
    CREATE TABLE ai_usage (
        id INTEGER PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        search_id INTEGER,
        step TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cached_input_tokens INTEGER NOT NULL,
        reasoning_tokens INTEGER NOT NULL,
        web_searches INTEGER NOT NULL
    );
    CREATE INDEX ai_usage_created_at ON ai_usage (created_at);
    CREATE INDEX ai_usage_search_id ON ai_usage (search_id);
    """,
]


def db_path(folder: Path | None = None) -> Path:
    return (folder if folder is not None else ensure_data_dir()) / DB_FILENAME


@contextmanager
def connect(folder: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open the database, bring its tables up to date, and commit on success."""
    conn = sqlite3.connect(db_path(folder), timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _migrate(conn)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
        conn.executescript(f"BEGIN; {script}; PRAGMA user_version = {number}; COMMIT;")
