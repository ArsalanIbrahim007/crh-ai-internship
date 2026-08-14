"""RRF fusion arithmetic — no index required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from retrieval.hybrid import rrf_fuse


def rows(ids, key):
    return [{"chunk_id": c, key: i, "text": c} for i, c in enumerate(ids, 1)]


def test_chunk_in_both_lists_outranks_either_alone():
    d = rows(["a", "b", "c"], "dense_rank")
    s = rows(["c", "d", "e"], "sparse_rank")
    fused = rrf_fuse(d, s)
    assert fused[0]["chunk_id"] == "c"       # rank 3 + rank 1 beats rank 1 alone
    assert fused[0]["retriever"] == "dense+sparse"


def test_single_retriever_results_are_kept():
    fused = rrf_fuse(rows(["a"], "dense_rank"), [])
    assert len(fused) == 1
    assert fused[0]["retriever"] == "dense"


def test_scores_are_monotonically_decreasing():
    d = rows([f"d{i}" for i in range(10)], "dense_rank")
    s = rows([f"s{i}" for i in range(10)], "sparse_rank")
    fused = rrf_fuse(d, s)
    scores = [f["rrf_score"] for f in fused]
    assert scores == sorted(scores, reverse=True)


def test_fused_ranks_are_contiguous():
    fused = rrf_fuse(rows(["a", "b"], "dense_rank"),
                     rows(["b", "c"], "sparse_rank"))
    assert [f["fused_rank"] for f in fused] == list(range(1, len(fused) + 1))


def test_k_limits_output():
    d = rows([f"x{i}" for i in range(20)], "dense_rank")
    assert len(rrf_fuse(d, [], k=5)) == 5


def test_both_empty_returns_empty():
    assert rrf_fuse([], []) == []