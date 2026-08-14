"""Full retrieval pipeline: hybrid search -> rerank -> parent expansion.

Kept separate from rag/ so retrieval can be benchmarked without an LLM in the
loop. Everything downstream consumes retrieve().
"""
from __future__ import annotations

import time

from config import FINAL_K, FUSED_K
from retrieval import hybrid, rerank
from retrieval.filters import Filter
from retrieval.store import parents_table


def fetch_parents(chunks: list[dict]) -> dict[str, str]:
    """Parent-child retrieval: search on precise child chunks, generate from
    the wider parent window so the model sees surrounding context."""
    ids = sorted({c["parent_id"] for c in chunks})
    if not ids:
        return {}
    quoted = ", ".join("'" + i.replace("'", "") + "'" for i in ids)
    rows = (parents_table().search()
            .where(f"parent_id IN ({quoted})")
            .limit(len(ids))
            .to_list())
    return {r["parent_id"]: r["text"] for r in rows}


def retrieve(query: str, top_k: int = FINAL_K, candidates: int = FUSED_K,
             user_filter: Filter | None = None, scope: Filter | None = None,
             use_reranker: bool = True, expand_parents: bool = True) -> dict:
    t0 = time.perf_counter()

    fused = hybrid.search(query, k=candidates,
                          user_filter=user_filter, scope=scope)
    rows = fused["results"]
    # Near-duplicate suppression. The corpus contains re-sent messages and
    # thread digests that re-quote the same body, and showing the same text
    # twice in eight results is a visible quality defect.
    seen: set[str] = set()
    deduped = []
    for r in rows:
        fp = " ".join(r["text"].split())[:300].lower()
        if fp in seen:
            continue
        seen.add(fp)
        deduped.append(r)
    dropped = len(rows) - len(deduped)
    rows = deduped

    if use_reranker and rows:
        reranked = rerank.rerank(query, rows, top_k=top_k)
        rows = reranked["results"]
        rerank_stats = reranked["stats"]
    else:
        rows = rows[:top_k]
        for i, r in enumerate(rows, 1):
            r["final_rank"] = i
            r["rerank_score"] = r.get("rrf_score", 0.0)
            r["rank_delta"] = 0
        rerank_stats = {"reranked": 0, "latency_ms": 0.0}

    if expand_parents and rows:
        parents = fetch_parents(rows)
        for r in rows:
            r["parent_text"] = parents.get(r["parent_id"], r["text"])

    return {
        "query": query,
        "results": rows,
        "stats": {
            **fused["stats"],
            "rerank": rerank_stats,
            "deduped": dropped,
            "total_latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    }