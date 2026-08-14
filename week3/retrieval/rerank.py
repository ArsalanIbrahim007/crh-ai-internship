"""Cross-encoder reranking.

The bi-encoder embeds query and passage independently, so it never sees them
together. A cross-encoder scores the pair jointly and is far more accurate at
the cost of running once per candidate — which is why it reranks 50 rather
than searching 100,000.

The same model doubles as the grounding scorer in rag/grounding.py: scoring
an answer sentence against its cited chunk is the same pairwise-relevance
problem, so no separate NLI model is needed.
"""
from __future__ import annotations

import gc
import time
from functools import lru_cache
from typing import Sequence

from config import DEVICE, FINAL_K, RERANK_BATCH, RERANK_MODEL

MAX_PAIR_TOKENS = 512


@lru_cache(maxsize=1)
def get_model():
    """Direct transformers, not sentence_transformers.CrossEncoder.

    The CrossEncoder wrapper is incompatible with transformers v5 — it hands
    a BatchEncoding to a forward pass that expects a tensor. Calling the
    sequence-classification head directly is simpler and version-stable.
    """
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = DEVICE if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(RERANK_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL)
    model = model.to(device)
    if device == "cuda":
        model = model.half()
    model.eval()
    return tokenizer, model, device


def score_pairs(query: str, passages: Sequence[str],
                batch_size: int = RERANK_BATCH) -> list[float]:
    """Raw cross-encoder logits for (query, passage) pairs."""
    if not passages:
        return []

    import torch

    tokenizer, model, device = get_model()
    scores: list[float] = []

    with torch.inference_mode():
        for start in range(0, len(passages), batch_size):
            batch = passages[start:start + batch_size]
            enc = tokenizer(
                [query] * len(batch),
                list(batch),
                padding=True,
                truncation=True,
                max_length=MAX_PAIR_TOKENS,
                return_tensors="pt",
            ).to(device)
            logits = model(**enc).logits.view(-1).float()
            scores.extend(logits.cpu().tolist())

    return scores


def normalise(scores: Sequence[float]) -> list[float]:
    """Logits -> 0..1 via sigmoid. bge-reranker-base emits unbounded logits;
    the UI needs a bounded confidence figure."""
    import math
    return [1.0 / (1.0 + math.exp(-s)) for s in scores]


def rerank(query: str, candidates: list[dict], top_k: int = FINAL_K,
           text_field: str = "text") -> dict:
    """Reorder candidates by cross-encoder relevance."""
    if not candidates:
        return {"results": [], "stats": {"reranked": 0, "latency_ms": 0.0}}

    t0 = time.perf_counter()
    raw = score_pairs(query, [c[text_field] for c in candidates])
    probs = normalise(raw)

    for c, r, p in zip(candidates, raw, probs):
        c["rerank_logit"] = r
        c["rerank_score"] = p

    ordered = sorted(candidates, key=lambda c: c["rerank_logit"], reverse=True)
    for rank, c in enumerate(ordered, 1):
        c["final_rank"] = rank
        c["rank_delta"] = c.get("fused_rank", rank) - rank

    elapsed = (time.perf_counter() - t0) * 1000
    top = ordered[:top_k]

    return {
        "results": top,
        "stats": {
            "reranked": len(candidates),
            "returned": len(top),
            "latency_ms": round(elapsed, 1),
            "top_score": round(top[0]["rerank_score"], 4) if top else 0.0,
            "promoted": sum(1 for c in top if c["rank_delta"] > 0),
        },
    }


def release() -> None:
    """Free reranker VRAM. Called between the ingest and serve phases."""
    import torch

    get_model.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()