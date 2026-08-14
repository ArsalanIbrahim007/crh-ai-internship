"""Query analytics.

Every answered query writes one row. The dashboard reads aggregates from here
rather than recomputing, so the analytics view costs one SQL round trip.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from config import PROCESSED

DB = PROCESSED / "analytics.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            REAL NOT NULL,
    session_id    TEXT,
    role          TEXT,
    question      TEXT NOT NULL,
    search_query  TEXT,
    model         TEXT,
    fell_back     INTEGER DEFAULT 0,
    sources_used  INTEGER DEFAULT 0,
    coverage      REAL DEFAULT 0,
    confidence    REAL DEFAULT 0,
    verdict       TEXT,
    flagged       INTEGER DEFAULT 0,
    dense_hits    INTEGER DEFAULT 0,
    sparse_hits   INTEGER DEFAULT 0,
    overlap       INTEGER DEFAULT 0,
    retrieval_ms  REAL DEFAULT 0,
    rerank_ms     REAL DEFAULT 0,
    generation_ms REAL DEFAULT 0,
    total_ms      REAL DEFAULT 0,
    filters       TEXT
);
CREATE INDEX IF NOT EXISTS idx_q_ts   ON queries(ts);
CREATE INDEX IF NOT EXISTS idx_q_role ON queries(role);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(DB), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def record(result: dict, role: str | None, session_id: str | None,
           filters: dict | None = None) -> None:
    s = result.get("stats", {})
    r = s.get("retrieval", {})
    t = s.get("timings_ms", {})
    try:
        with connect() as conn:
            conn.execute(
                """INSERT INTO queries
                   (ts, session_id, role, question, search_query, model,
                    fell_back, sources_used, coverage, confidence, verdict,
                    flagged, dense_hits, sparse_hits, overlap, retrieval_ms,
                    rerank_ms, generation_ms, total_ms, filters)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (time.time(), session_id, role, result.get("question", ""),
                 result.get("search_query", ""), result.get("model"),
                 int(bool(result.get("fell_back"))), s.get("sources_used", 0),
                 s.get("citation_coverage", 0.0), s.get("confidence", 0.0),
                 s.get("verdict", ""), s.get("flagged_sentences", 0),
                 r.get("dense_hits", 0), r.get("sparse_hits", 0),
                 r.get("overlap", 0), t.get("retrieval_ms", 0.0),
                 (r.get("rerank") or {}).get("latency_ms", 0.0),
                 t.get("generation_ms", 0.0), s.get("total_ms", 0.0),
                 json.dumps(filters or {})),
            )
    except Exception:
        pass          # analytics must never break a query


def summary() -> dict:
    with connect() as conn:
        agg = conn.execute(
            """SELECT COUNT(*) n,
                      AVG(confidence) conf, AVG(coverage) cov,
                      AVG(total_ms) lat, AVG(retrieval_ms) ret,
                      AVG(generation_ms) gen, SUM(flagged) flagged,
                      SUM(fell_back) fallbacks
               FROM queries"""
        ).fetchone()
        by_role = conn.execute(
            "SELECT role, COUNT(*) n, AVG(confidence) conf "
            "FROM queries GROUP BY role ORDER BY n DESC"
        ).fetchall()
        by_verdict = conn.execute(
            "SELECT verdict, COUNT(*) n FROM queries GROUP BY verdict"
        ).fetchall()
        recent = conn.execute(
            "SELECT ts, question, role, confidence, total_ms, model "
            "FROM queries ORDER BY ts DESC LIMIT 20"
        ).fetchall()
        latencies = conn.execute(
            "SELECT total_ms FROM queries ORDER BY total_ms"
        ).fetchall()

    lat = [r["total_ms"] for r in latencies]
    def pct(p: float) -> float:
        return round(lat[min(int(len(lat) * p), len(lat) - 1)], 1) if lat else 0.0

    return {
        "total_queries": agg["n"] or 0,
        "avg_confidence": round(agg["conf"] or 0, 3),
        "avg_coverage": round(agg["cov"] or 0, 3),
        "avg_latency_ms": round(agg["lat"] or 0, 1),
        "avg_retrieval_ms": round(agg["ret"] or 0, 1),
        "avg_generation_ms": round(agg["gen"] or 0, 1),
        "flagged_sentences": agg["flagged"] or 0,
        "model_fallbacks": agg["fallbacks"] or 0,
        "p50_ms": pct(0.5), "p95_ms": pct(0.95),
        "by_role": [{"role": r["role"], "queries": r["n"],
                     "confidence": round(r["conf"] or 0, 3)} for r in by_role],
        "by_verdict": [{"verdict": r["verdict"], "count": r["n"]}
                       for r in by_verdict],
        "recent": [dict(r) for r in recent],
    }