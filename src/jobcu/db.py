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
    # 2: Searches, so usage and results can be linked to the search they belong to.
    """
    CREATE TABLE searches (
        id INTEGER PRIMARY KEY,
        started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        finished_at TEXT,
        status TEXT NOT NULL,
        form_json TEXT NOT NULL
    );
    """,
    # 3: Requests sent to job sources per day, so free daily and monthly limits are kept.
    """
    CREATE TABLE source_requests (
        day TEXT NOT NULL,
        source TEXT NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY (day, source)
    );
    """,
    # 4: Jobs remembered between searches (HANDOVER section 12): which jobs were shown
    # before (for the "New" badge), their Saved / Applied / Not interested state, and
    # each search's results so they can be shown again.
    """
    CREATE TABLE jobs (
        id INTEGER PRIMARY KEY,
        first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        first_seen_search_id INTEGER,
        title TEXT NOT NULL,
        company TEXT
    );
    CREATE TABLE job_keys (
        key TEXT PRIMARY KEY,
        job_id INTEGER NOT NULL REFERENCES jobs (id)
    );
    CREATE INDEX job_keys_job_id ON job_keys (job_id);
    CREATE TABLE job_states (
        job_id INTEGER PRIMARY KEY REFERENCES jobs (id),
        saved INTEGER NOT NULL DEFAULT 0,
        applied INTEGER NOT NULL DEFAULT 0,
        dismissed INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
    CREATE TABLE search_results (
        search_id INTEGER PRIMARY KEY REFERENCES searches (id),
        result_json TEXT NOT NULL
    );
    -- The latest card of each job, so Saved and Applied jobs can be listed any time.
    CREATE TABLE job_cards (
        job_id INTEGER PRIMARY KEY REFERENCES jobs (id),
        card_json TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
    """,
    # 5: What the AI understood from the CV and cover letter, kept only for exactly these
    # documents, prompt and model, so unchanged documents aren't read again (DECISIONS.md).
    """
    CREATE TABLE profile_cache (
        key TEXT PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        profile_json TEXT NOT NULL
    );
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
    if conn.execute("PRAGMA user_version").fetchone()[0] >= len(MIGRATIONS):
        return
    # Several parts of Jobcu may open the database at the same moment. BEGIN IMMEDIATE lets
    # only one of them update the tables; the others wait, then see the work is done.
    previous = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, script in enumerate(MIGRATIONS[current:], start=current + 1):
                for statement in _statements(script):
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {number}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.isolation_level = previous


def _statements(script: str) -> list[str]:
    statements, pending = [], ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            if pending.strip():
                statements.append(pending.strip())
            pending = ""
    if pending.strip() and not all(
        part.strip().startswith("--") or not part.strip() for part in pending.splitlines()
    ):
        statements.append(pending.strip())
    return statements
