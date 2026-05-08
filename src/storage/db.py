"""SQLite database connection management for Relay.

Single-file, local-first storage. The schema is intentionally simple and
strictly typed. All stores accept a Database instance, which makes
testing with a temporary database trivial.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id          TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    remind_at   TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    completed   INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    source      TEXT,
    metadata    TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    tags        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    source      TEXT,
    metadata    TEXT
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    location     TEXT,
    start_time   TEXT NOT NULL,
    end_time     TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    source       TEXT,
    metadata     TEXT
);

CREATE TABLE IF NOT EXISTS action_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    source        TEXT,
    raw_input     TEXT,
    normalized    TEXT,
    route         TEXT,
    tool_name     TEXT,
    args          TEXT,
    status        TEXT NOT NULL,
    message       TEXT,
    error         TEXT,
    plan_id       TEXT,
    step_index    INTEGER,
    metadata      TEXT
);

CREATE TABLE IF NOT EXISTS pending_actions (
    id              TEXT PRIMARY KEY,
    tool_name       TEXT NOT NULL,
    args            TEXT NOT NULL,
    preview         TEXT,
    safety_level    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    expires_at      TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    source          TEXT,
    metadata        TEXT
);

CREATE INDEX IF NOT EXISTS idx_reminders_remind_at  ON reminders(remind_at);
CREATE INDEX IF NOT EXISTS idx_reminders_completed  ON reminders(completed);
CREATE INDEX IF NOT EXISTS idx_notes_created_at     ON notes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_start_time    ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_logs_created_at      ON action_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pending_status       ON pending_actions(status);
"""


class Database:
    """Thread-safe SQLite wrapper.

    A single connection is shared across threads using the GIL plus an
    explicit lock for write paths. SQLite's WAL mode gives us decent
    concurrency for the small footprint Relay needs.
    """

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_default_db: Optional[Database] = None
_default_db_lock = threading.Lock()


def get_default_db() -> Database:
    """Return the process-wide default database.

    Resolves the path from RELAY_DB env var, then ~/.relay/data/relay.db.
    """
    global _default_db
    with _default_db_lock:
        if _default_db is None:
            path = os.environ.get("RELAY_DB")
            if not path:
                # Lazy import to avoid heavy config side effects during tests
                from ..config.settings import config
                path = str(config.get_data_dir() / "relay.db")
            _default_db = Database(path)
        return _default_db


def set_default_db(db: Optional[Database]) -> None:
    """Replace the process-wide default database (for tests)."""
    global _default_db
    with _default_db_lock:
        _default_db = db
