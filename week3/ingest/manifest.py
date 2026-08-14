"""Resumable ingest bookkeeping.

The manifest is the source of truth for *what has been indexed*. build_index
consults it before every batch, so an interrupted run resumes instead of
restarting. This is the single most important file in the ingest path.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from config import MANIFEST_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    fmt          TEXT NOT NULL,
    title        TEXT,
    author       TEXT,
    department   TEXT,
    created_at   TEXT,
    n_chunks     INTEGER DEFAULT 0,
    n_chars      INTEGER DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',
    error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_docs_dept   ON documents(department);

CREATE TABLE IF NOT EXISTS runs (
    run_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    n_docs     INTEGER DEFAULT 0,
    n_chunks   INTEGER DEFAULT 0,
    note       TEXT
);
"""


@contextmanager
def connect(path: Path | str = MANIFEST_DB) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(path: Path | str = MANIFEST_DB) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def indexed_ids(path: Path | str = MANIFEST_DB) -> set[str]:
    """Doc ids already committed to the vector store."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT doc_id FROM documents WHERE status = 'indexed'"
        ).fetchall()
    return {r["doc_id"] for r in rows}


def mark_indexed(records: Iterable[dict], path: Path | str = MANIFEST_DB) -> int:
    rows = [
        (
            r["doc_id"], r["source"], r["fmt"], r.get("title"), r.get("author"),
            r.get("department"), r.get("created_at"), r.get("n_chunks", 0),
            r.get("n_chars", 0),
        )
        for r in records
    ]
    if not rows:
        return 0
    with connect(path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO documents
               (doc_id, source, fmt, title, author, department, created_at,
                n_chunks, n_chars, status, error)
               VALUES (?,?,?,?,?,?,?,?,?,'indexed',NULL)""",
            rows,
        )
    return len(rows)


def mark_failed(doc_id: str, source: str, fmt: str, error: str,
                path: Path | str = MANIFEST_DB) -> None:
    with connect(path) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO documents
               (doc_id, source, fmt, status, error)
               VALUES (?,?,?,'failed',?)""",
            (doc_id, source, fmt, error[:500]),
        )


def stats(path: Path | str = MANIFEST_DB) -> dict:
    with connect(path) as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*)                                   AS docs,
                 COALESCE(SUM(n_chunks), 0)                 AS chunks,
                 COALESCE(SUM(n_chars), 0)                  AS chars,
                 SUM(status = 'failed')                     AS failed
               FROM documents"""
        ).fetchone()
        by_fmt = conn.execute(
            "SELECT fmt, COUNT(*) AS n FROM documents "
            "WHERE status='indexed' GROUP BY fmt"
        ).fetchall()
        by_dept = conn.execute(
            "SELECT department, COUNT(*) AS n FROM documents "
            "WHERE status='indexed' GROUP BY department ORDER BY n DESC LIMIT 15"
        ).fetchall()
    return {
        "documents": row["docs"],
        "chunks": row["chunks"],
        "characters": row["chars"],
        "failed": row["failed"] or 0,
        "by_format": {r["fmt"]: r["n"] for r in by_fmt},
        "by_department": {r["department"]: r["n"] for r in by_dept},
    }