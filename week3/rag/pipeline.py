"""End-to-end RAG: retrieve -> compress -> generate -> cite -> verify.

Every stage reports its own latency so the UI can show where time went, and
the grounding pass runs after generation rather than trusting the prompt.
"""
from __future__ import annotations

import time

from config import FINAL_K, FUSED_K
from rag import citations, compress, grounding, llm, memory, prompts
from retrieval import pipeline as retrieval_pipeline
from retrieval.filters import Filter

NO_ANSWER = ("The indexed sources do not contain enough information to answer "
             "this question.")


def rewrite_followup(question: str, history: list[dict]) -> str:
    if not history:
        return question
    turns = "\n".join(f"{h['role']}: {h['content'][:300]}" for h in history)
    try:
        out = llm.chat([
            {"role": "system", "content": prompts.REWRITE_SYSTEM},
            {"role": "user", "content": f"{turns}\n\nFollow-up: {question}"},
        ], max_tokens=120)
        rewritten = out["text"].strip().strip('"')
        return rewritten if 3 <= len(rewritten) <= 300 else question
    except Exception:
        return question


def answer(question: str, role_scope: Filter | None = None,
           user_filter: Filter | None = None, session_id: str | None = None,
           model: str | None = None, top_k: int = FINAL_K,
           candidates: int = FUSED_K, use_reranker: bool = True,
           use_compression: bool = True) -> dict:
    t0 = time.perf_counter()
    timings: dict[str, float] = {}

    history = memory.history_for_prompt(session_id) if session_id else []

    t = time.perf_counter()
    search_query = rewrite_followup(question, history) if history else question
    timings["rewrite_ms"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    retrieved = retrieval_pipeline.retrieve(
        search_query, top_k=top_k, candidates=candidates,
        user_filter=user_filter, scope=role_scope,
        use_reranker=use_reranker,
    )
    timings["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
    chunks = retrieved["results"]

    if not chunks:
        return _empty(question, search_query, retrieved, timings, t0)

    t = time.perf_counter()
    compression = compress.compress_all(search_query, chunks,
                                        enabled=use_compression)
    timings["compression_ms"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    completion = llm.chat([
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.build_user_message(
            question, chunks, history)},
    ], model=model)
    timings["generation_ms"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    parsed = citations.parse(completion["text"], chunks)
    parsed = grounding.score_answer(parsed, chunks)
    timings["verification_ms"] = round((time.perf_counter() - t) * 1000, 1)

    if session_id:
        memory.append(session_id, "user", question)
        memory.append(session_id, "assistant", parsed["answer"],
                      meta={"confidence": parsed["stats"]["confidence"],
                            "sources": len(parsed["sources"])})

    return {
        "question": question,
        "search_query": search_query,
        "answer": parsed["answer"],
        "sentences": parsed["sentences"],
        "sources": parsed["sources"],
        "model": completion["model"],
        "fell_back": completion["fell_back"],
        "stats": {
            **parsed["stats"],
            "retrieval": retrieved["stats"],
            "compression": compression,
            "tokens": {
                "prompt": completion["prompt_tokens"],
                "completion": completion["completion_tokens"],
            },
            "timings_ms": timings,
            "total_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    }


def _empty(question, search_query, retrieved, timings, t0) -> dict:
    return {
        "question": question,
        "search_query": search_query,
        "answer": NO_ANSWER,
        "sentences": [{"text": NO_ANSWER, "citations": [], "uncited": True,
                       "grounding": None, "flagged": False}],
        "sources": [],
        "model": None,
        "fell_back": False,
        "stats": {
            "sentences": 1, "cited_sentences": 0, "citation_coverage": 0.0,
            "sources_used": 0, "sources_offered": 0, "invalid_markers": [],
            "confidence": 0.0, "verdict": "no sources matched",
            "flagged_sentences": 0,
            "retrieval": retrieved["stats"],
            "timings_ms": timings,
            "total_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    }