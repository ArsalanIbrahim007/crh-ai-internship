"""Persistent long-term memory backed by SQLite + FTS5.

Stores three categories:
  initiatives   — past project briefs and outcomes
  decisions     — architecture decision records
  retrospectives — lessons from failed reflection loops

Every agent can recall past context.  Only CEO/PM agents write to memory.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from config import MEMORY_DB

MemoryCategory = Literal["initiative", "decision", "retrospective"]


@dataclass
class MemoryEntry:
    id: int
    category: MemoryCategory
    title: str
    content: str
    metadata: dict
    timestamp: float


class LongTermMemory:
    """SQLite-backed episodic + semantic memory with full-text search."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = str(db_path or MEMORY_DB)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                category  TEXT NOT NULL,
                title     TEXT NOT NULL,
                content   TEXT NOT NULL,
                metadata  TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title, content, content=memories, content_rowid=id
            );

            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, content)
                VALUES (new.id, new.title, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, content)
                VALUES ('delete', old.id, old.title, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, content)
                VALUES ('delete', old.id, old.title, old.content);
                INSERT INTO memories_fts(rowid, title, content)
                VALUES (new.id, new.title, new.content);
            END;
        """)
        conn.commit()

    def store(
        self,
        category: MemoryCategory,
        title: str,
        content: str,
        metadata: dict | None = None,
    ) -> int:
        """Write a memory entry. Returns the row ID."""
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO memories (category, title, content, metadata, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (category, title, content, json.dumps(metadata or {}), time.time()),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def recall(
        self,
        query: str,
        category: MemoryCategory | None = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Full-text search across memories, optionally filtered by category."""
        conn = self._get_conn()

        if category:
            rows = conn.execute(
                "SELECT m.id, m.category, m.title, m.content, m.metadata, m.timestamp "
                "FROM memories m "
                "JOIN memories_fts f ON m.id = f.rowid "
                "WHERE memories_fts MATCH ? AND m.category = ? "
                "ORDER BY rank LIMIT ?",
                (query, category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT m.id, m.category, m.title, m.content, m.metadata, m.timestamp "
                "FROM memories m "
                "JOIN memories_fts f ON m.id = f.rowid "
                "WHERE memories_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (query, limit),
            ).fetchall()

        return [
            MemoryEntry(
                id=r[0],
                category=r[1],
                title=r[2],
                content=r[3],
                metadata=json.loads(r[4]),
                timestamp=r[5],
            )
            for r in rows
        ]

    def list_recent(
        self,
        category: MemoryCategory | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Return the most recent memories."""
        conn = self._get_conn()
        if category:
            rows = conn.execute(
                "SELECT id, category, title, content, metadata, timestamp "
                "FROM memories WHERE category = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, category, title, content, metadata, timestamp "
                "FROM memories ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            MemoryEntry(
                id=r[0], category=r[1], title=r[2], content=r[3],
                metadata=json.loads(r[4]), timestamp=r[5],
            )
            for r in rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
