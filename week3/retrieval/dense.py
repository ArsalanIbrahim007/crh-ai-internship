"""Dense vector retrieval."""
from __future__ import annotations

import time

from config import DENSE_K
from ingest.embed import encode_query
from retrieval.filters import Filter, build_where
from retrieval.store import chunks_table

COLUMNS = ["chunk_id", "doc_id", "parent_id", "text", "title", "author",
           "department", "classification", "fmt", "source", "created_at",
           "year", "page", "custodian", "thread_key"]


def search(query: str, k: int = DENSE_K, user_filter: Filter | None = None,
           scope: Filter | None = None, nprobes: int = 24) -> list[dict]:
    tbl = chunks_table()
    where = build_where(user_filter, scope)

    t0 = time.perf_counter()
    q = tbl.search(encode_query(query), vector_column_name="vector")
    q = q.metric("cosine").nprobes(nprobes)
    if where:
        # prefilter: apply the predicate before ANN, not after, or a
        # restrictive filter returns almost nothing.
        q = q.where(where, prefilter=True)
    rows = q.select(COLUMNS).limit(k).to_list()
    latency = (time.perf_counter() - t0) * 1000

    for rank, r in enumerate(rows, 1):
        r["dense_rank"] = rank
        # LanceDB returns cosine *distance*; convert to similarity
        r["dense_score"] = 1.0 - float(r.pop("_distance", 0.0))
        r["retriever"] = "dense"
    if rows:
        rows[0]["_latency_ms"] = latency
    return rows