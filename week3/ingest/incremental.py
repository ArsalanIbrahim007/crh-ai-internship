"""Single-document ingest for uploads.

The batch pipeline assumes a static corpus. This adds one document to a live
index: same loaders, same chunker, same embedder, appended to the existing
LanceDB tables. The ANN index is not rebuilt — new rows are searchable via
flat scan until the next full build, which is correct for a handful of
uploads and wrong for thousands.
"""
from __future__ import annotations

from pathlib import Path

from ingest import manifest
from ingest.chunker import chunk_document
from ingest.embed import encode_passages
from ingest.loaders import LOADERS, Document
from retrieval.store import chunks_table, parents_table


def _year(created_at: str) -> int:
    try:
        return int(created_at[:4])
    except Exception:
        return 0


def ingest_file(path: Path, department: str | None = None) -> dict:
    """Load, chunk, embed and index one file. Returns a summary."""
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"unsupported format: {path.suffix}")

    doc: Document = loader(path)
    if department:
        doc.department = department          # explicit beats inferred

    if not doc.text.strip():
        raise ValueError("no extractable text")

    parents, chunks = chunk_document(doc)
    if not chunks:
        raise ValueError("document produced no chunks")

    vectors = encode_passages([c.text for c in chunks])
    year = _year(doc.created_at)

    chunks_table().add([{
        "chunk_id": c.chunk_id, "doc_id": c.doc_id, "parent_id": c.parent_id,
        "ordinal": int(c.ordinal), "text": c.text, "vector": v.tolist(),
        "title": doc.title or path.stem, "author": doc.author or "",
        "department": doc.department, "classification": doc.classification,
        "fmt": doc.fmt, "source": str(path), "created_at": doc.created_at or "",
        "year": year, "page": int(c.page or 0), "custodian": "",
        "thread_key": "", "recipients": "",
    } for c, v in zip(chunks, vectors)])

    parents_table().add([{
        "parent_id": p.parent_id, "doc_id": p.doc_id,
        "ordinal": int(p.ordinal), "text": p.text,
    } for p in parents])

    manifest.mark_indexed([{
        "doc_id": doc.doc_id, "source": str(path), "fmt": doc.fmt,
        "title": doc.title, "author": doc.author,
        "department": doc.department, "created_at": doc.created_at,
        "n_chunks": len(chunks), "n_chars": doc.n_chars,
    }])

    return {
        "doc_id": doc.doc_id, "title": doc.title or path.stem,
        "fmt": doc.fmt, "department": doc.department,
        "classification": doc.classification,
        "chunks": len(chunks), "parents": len(parents),
        "chars": doc.n_chars,
    }