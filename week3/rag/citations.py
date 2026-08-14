"""Citation extraction and verification.

The model emits [n] markers; this module maps them back to chunks, drops
markers that point nowhere, and reports which sources were actually used.
Unverified citations are a hallucination vector, so they are removed rather
than displayed.
"""
from __future__ import annotations

import re

MARKER = re.compile(r"[\[\u3010\uFF3B]\s*(\d{1,2})\s*[\]\u3011\uFF3D]")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in SENTENCE.split(text) if s.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def parse(answer: str, chunks: list[dict]) -> dict:
    """Map markers to sources, strip invalid ones, return per-sentence spans."""
    # Some models emit CJK full-width brackets. Normalise before parsing so
    # the marker regex, the stripper and the UI all see one form.
    answer = (answer.replace("\u3010", "[").replace("\u3011", "]")
                    .replace("\uFF3B", "[").replace("\uFF3D", "]"))

    valid = set(range(1, len(chunks) + 1))
    invalid: set[int] = set()

    for m in MARKER.finditer(answer):
        n = int(m.group(1))
        if n not in valid:
            invalid.add(n)

    cleaned = answer
    for n in invalid:
        cleaned = cleaned.replace(f"[{n}]", "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    sentences = []
    used: set[int] = set()
    for sent in split_sentences(cleaned):
        nums = sorted({int(m.group(1)) for m in MARKER.finditer(sent)}
                      & valid)
        used.update(nums)
        sentences.append({
            "text": sent,
            "citations": nums,
            "uncited": not nums,
        })

    sources = []
    for i, c in enumerate(chunks, 1):
        if i in used:
            sources.append({
                "n": i,
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "title": c.get("title") or "untitled",
                "author": c.get("author", ""),
                "department": c.get("department", ""),
                "fmt": c.get("fmt", ""),
                "source": c.get("source", ""),
                "created_at": c.get("created_at", ""),
                "page": c.get("page") or None,
                "text": c["text"],
                "retrieval_score": round(c.get("rerank_score", 0.0), 4),
            })

    total = len(sentences)
    cited = sum(1 for s in sentences if s["citations"])
    return {
        "answer": cleaned,
        "sentences": sentences,
        "sources": sources,
        "stats": {
            "sentences": total,
            "cited_sentences": cited,
            "citation_coverage": round(cited / total, 3) if total else 0.0,
            "sources_used": len(sources),
            "sources_offered": len(chunks),
            "invalid_markers": sorted(invalid),
        },
    }