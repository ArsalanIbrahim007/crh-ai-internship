"""Token-aware chunking with parent-child linkage.

Children are what gets embedded and searched. Parents are what gets shown to
the LLM. This is the whole point of parent-child retrieval: search precision
at child granularity, generation context at parent granularity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from config import CHUNK_OVERLAP, CHUNK_TOKENS, MIN_CHUNK_CHARS
from ingest.loaders import Document

PAGE_ANCHOR = re.compile(r"\[\[page:(\d+)\]\]")
PARENT_TOKENS = CHUNK_TOKENS * 3


@lru_cache(maxsize=1)
def _encoder():
    import tiktoken
    return tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    parent_id: str
    ordinal: int
    text: str
    page: int | None = None


@dataclass
class Parent:
    parent_id: str
    doc_id: str
    ordinal: int
    text: str


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def _pack(units: list[str], budget: int) -> list[str]:
    """Greedily pack paragraphs up to a token budget, splitting any single
    paragraph that overflows on its own."""
    enc = _encoder()
    out: list[str] = []
    buf: list[str] = []
    buf_tokens = 0

    for unit in units:
        n = len(enc.encode(unit))
        if n > budget:
            if buf:
                out.append("\n\n".join(buf))
                buf, buf_tokens = [], 0
            ids = enc.encode(unit)
            step = budget - CHUNK_OVERLAP
            for start in range(0, len(ids), step):
                piece = enc.decode(ids[start:start + budget]).strip()
                if piece:
                    out.append(piece)
            continue
        if buf_tokens + n > budget and buf:
            out.append("\n\n".join(buf))
            buf, buf_tokens = [], 0
        buf.append(unit)
        buf_tokens += n

    if buf:
        out.append("\n\n".join(buf))
    return out


def _page_of(text: str, fallback: int | None) -> int | None:
    m = PAGE_ANCHOR.search(text)
    return int(m.group(1)) if m else fallback


def chunk_document(doc: Document) -> tuple[list[Parent], list[Chunk]]:
    paragraphs = _split_paragraphs(doc.text)
    if not paragraphs:
        return [], []

    parent_texts = _pack(paragraphs, PARENT_TOKENS)
    parents: list[Parent] = []
    chunks: list[Chunk] = []
    ordinal = 0
    current_page: int | None = None

    for p_idx, ptext in enumerate(parent_texts):
        parent_id = f"{doc.doc_id}:p{p_idx}"
        parents.append(Parent(parent_id, doc.doc_id, p_idx,
                              PAGE_ANCHOR.sub("", ptext).strip()))

        for ctext in _pack(_split_paragraphs(ptext), CHUNK_TOKENS):
            current_page = _page_of(ctext, current_page)
            clean = PAGE_ANCHOR.sub("", ctext).strip()
            if len(clean) < MIN_CHUNK_CHARS:
                continue
            chunks.append(Chunk(
                chunk_id=f"{doc.doc_id}:c{ordinal}",
                doc_id=doc.doc_id,
                parent_id=parent_id,
                ordinal=ordinal,
                text=clean,
                page=current_page,
            ))
            ordinal += 1

    return parents, chunks


def chunk_stream(docs: Iterator[Document]) -> Iterator[tuple[Document, list[Parent], list[Chunk]]]:
    for doc in docs:
        parents, chunks = chunk_document(doc)
        if chunks:
            yield doc, parents, chunks