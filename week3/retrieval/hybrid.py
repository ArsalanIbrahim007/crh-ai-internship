"""Reciprocal-rank fusion of dense and sparse results.

RRF over score normalisation: cosine similarity and BM25 live on
incomparable scales, and any attempt to normalise them into one range is
arbitrary. Ranks are comparable by construction.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from config import DENSE_K, FUSED_K, RRF_K, SPARSE_K
from retrieval import dense, sparse
from retrieval.filters import Filter

_POOL = ThreadPoolExecutor(max_workers=2)


def rrf_fuse(dense_rows: list[dict], sparse_rows: list[dict],
             k: int = FUSED_K, rrf_k: int = RRF_K) -> list[dict]:
    merged: dict[str, dict] = {}

    for rows, rank_key in ((dense_rows, "dense_rank"),
                           (sparse_rows, "sparse_rank")):
        for r in rows:
            cid = r["chunk_id"]
            slot = merged.setdefault(cid, {**r, "rrf_score": 0.0,
                                            "retrievers": []})
            slot["rrf_score"] += 1.0 / (rrf_k + r[rank_key])
            slot["retrievers"].append("dense" if rank_key == "dense_rank"
                                      else "sparse")
            for f in ("dense_score", "sparse_score", "dense_rank", "sparse_rank"):
                if f in r:
                    slot[f] = r[f]

    out = sorted(merged.values(), key=lambda r: r["rrf_score"], reverse=True)
    for rank, r in enumerate(out, 1):
        r["fused_rank"] = rank
        r["retriever"] = "+".join(sorted(set(r["retrievers"])))
    return out[:k]


def search(query: str, k: int = FUSED_K, user_filter: Filter | None = None,
           scope: Filter | None = None,
           dense_k: int = DENSE_K, sparse_k: int = SPARSE_K) -> dict:
    """Both retrievers run concurrently — they hit different indices and the
    latency is dominated by whichever is slower, not their sum."""
    t0 = time.perf_counter()

    fut_d = _POOL.submit(dense.search, query, dense_k, user_filter, scope)
    fut_s = _POOL.submit(sparse.search, query, sparse_k, user_filter, scope)
    dense_rows, sparse_rows = fut_d.result(), fut_s.result()

    fused = rrf_fuse(dense_rows, sparse_rows, k=k)
    elapsed = (time.perf_counter() - t0) * 1000

    dense_ids = {r["chunk_id"] for r in dense_rows}
    sparse_ids = {r["chunk_id"] for r in sparse_rows}

    return {
        "results": fused,
        "stats": {
            "dense_hits": len(dense_rows),
            "sparse_hits": len(sparse_rows),
            "overlap": len(dense_ids & sparse_ids),
            "fused": len(fused),
            "latency_ms": round(elapsed, 1),
        },
    }