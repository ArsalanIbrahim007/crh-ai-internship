"""Context compression.

Parent windows are three times chunk size, so eight sources can exceed the
useful context. Sentences within each source are scored against the query with
the cross-encoder and the weakest are dropped — keeping the evidence that
matters rather than truncating at an arbitrary character count.
"""
from __future__ import annotations

from rag.citations import split_sentences
from retrieval.rerank import score_pairs

MIN_SENTENCES = 2


def compress_chunk(query: str, text: str, keep_ratio: float = 0.6,
                   max_chars: int = 1800) -> tuple[str, dict]:
    if len(text) <= max_chars:
        return text, {"compressed": False, "kept": 0, "total": 0}

    sentences = split_sentences(text)
    if len(sentences) <= MIN_SENTENCES:
        return text[:max_chars], {"compressed": True, "kept": len(sentences),
                                  "total": len(sentences)}

    scores = score_pairs(query, sentences)
    ranked = sorted(range(len(sentences)), key=lambda i: scores[i],
                    reverse=True)
    keep_n = max(MIN_SENTENCES, int(len(sentences) * keep_ratio))
    keep = sorted(ranked[:keep_n])          # restore reading order

    out, used = [], 0
    for i in keep:
        s = sentences[i]
        if used + len(s) > max_chars:
            break
        out.append(s)
        used += len(s)

    return " ".join(out), {"compressed": True, "kept": len(out),
                           "total": len(sentences)}


def compress_all(query: str, chunks: list[dict],
                 enabled: bool = True) -> dict:
    if not enabled:
        return {"chars_before": 0, "chars_after": 0, "compressed": 0}

    before = after = compressed = 0
    for c in chunks:
        text = c.get("parent_text") or c["text"]
        before += len(text)
        new_text, stats = compress_chunk(query, text)
        c["parent_text"] = new_text
        after += len(new_text)
        compressed += 1 if stats["compressed"] else 0

    return {
        "chars_before": before,
        "chars_after": after,
        "reduction": round(1 - after / before, 3) if before else 0.0,
        "compressed": compressed,
    }