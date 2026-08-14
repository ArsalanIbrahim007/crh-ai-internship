"""Prompt templates.

The citation contract is enforced by prompt and verified by code. The model is
told to cite with [n] markers; rag/citations.py then checks every marker
resolves to a real source and rag/grounding.py scores each sentence against
the chunk it cites. Prompting alone is not a guarantee.
"""
from __future__ import annotations

SYSTEM = """You are an enterprise knowledge assistant answering questions from an \
indexed document corpus.

Rules:
- Answer ONLY from the provided sources. If the sources do not contain the \
answer, say so plainly and stop.
- EVERY sentence containing a factual claim must end with its citation marker \
in ASCII square brackets, e.g. [3]. Do not group all citations at the end of a \
paragraph — attach them sentence by sentence. Use ASCII [ and ] only, never \
full-width brackets.
- Multiple sources for one claim: [1][4].
- Never invent source numbers. Never cite a source you did not use.
- Do not speculate, extrapolate, or add background knowledge from outside the \
sources.
- Be concise. Prefer specific figures, dates and names from the sources over \
general description."""


def format_sources(chunks: list[dict], use_parents: bool = True) -> str:
    blocks = []
    for i, c in enumerate(chunks, 1):
        text = c.get("parent_text") if use_parents else c["text"]
        text = text or c["text"]
        header = (f"[{i}] {c.get('title') or 'untitled'} "
                  f"| {c.get('department', '')} "
                  f"| {c.get('fmt', '')} "
                  f"| {(c.get('created_at') or '')[:10]}")
        blocks.append(f"{header}\n{text}")
    return "\n\n---\n\n".join(blocks)


def build_user_message(question: str, chunks: list[dict],
                       history: list[dict] | None = None) -> str:
    parts = []
    if history:
        turns = "\n".join(
            f"{h['role']}: {h['content'][:400]}" for h in history[-4:]
        )
        parts.append(f"Earlier in this conversation:\n{turns}\n")
    parts.append(f"SOURCES:\n\n{format_sources(chunks)}\n")
    parts.append(f"QUESTION: {question}")
    return "\n".join(parts)


REWRITE_SYSTEM = """Rewrite the user's follow-up question into a standalone \
search query using the conversation context. Output only the rewritten query, \
nothing else. If it is already standalone, output it unchanged."""

SELFQUERY_SYSTEM = """Extract structured search filters from the user's question.

Return ONLY a JSON object, no markdown fences, no commentary:
{"query": "the semantic part of the question with filter terms removed",
 "departments": [], "formats": [], "classifications": [],
 "year_from": null, "year_to": null}

Valid departments: Legal, Trading, Risk, HR, Finance, Compliance, IT, General
Valid formats: email, pdf, docx, html, csv
Valid classifications: internal, restricted

Only populate a field if the question clearly implies it. Empty list or null \
otherwise."""