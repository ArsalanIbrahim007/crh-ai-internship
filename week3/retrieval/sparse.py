"""BM25 keyword retrieval via LanceDB's native full-text index.

Dense retrieval fails on exact identifiers — ticker symbols, contract numbers,
surnames. That is what this is for, and it is why hybrid beats either alone.
"""
from __future__ import annotations

import re
import time

from config import SPARSE_K
from retrieval.dense import COLUMNS
from retrieval.filters import Filter, build_where
from retrieval.store import chunks_table

# Tantivy's query parser treats these as syntax; strip them from user input.
RESERVED = re.compile(r'[+\-&|!(){}\[\]^"~*?:\\/]')


def sanitize(query: str) -> str:
    cleaned = RESERVED.sub(" ", query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "*"


def search(query: str, k: int = SPARSE_K, user_filter: Filter | None = None,
           scope: Filter | None = None) -> list[dict]:
    tbl = chunks_table()
    where = build_where(user_filter, scope)

    t0 = time.perf_counter()
    try:
        q = tbl.search(sanitize(query), query_type="fts")
        if where:
            q = q.where(where)
        rows = q.select(COLUMNS).limit(k).to_list()
    except Exception:
        # A malformed FTS query must not take down the whole search.
        rows = []
    latency = (time.perf_counter() - t0) * 1000

    for rank, r in enumerate(rows, 1):
        r["sparse_rank"] = rank
        r["sparse_score"] = float(r.pop("_score", 0.0))
        r["retriever"] = "sparse"
    if rows:
        rows[0]["_latency_ms"] = latency
    return rows