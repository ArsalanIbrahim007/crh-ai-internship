"""Corpus -> chunks -> vectors -> LanceDB.

Resumable by design: the manifest is consulted before every batch and written
after every commit, so an interrupted run resumes at the last committed batch
rather than restarting. Interrupt it freely.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DEFAULT_DOC_LIMIT, EMBED_BATCH
from ingest import manifest
from ingest.chunker import chunk_document
from ingest.embed import encode_passages, release
from ingest.loaders import Document, load_directory, load_enron
from retrieval import store

COMMIT_EVERY = 2_000          # documents per LanceDB commit


def _year(created_at: str) -> int:
    try:
        return int(created_at[:4])
    except Exception:
        return 0


CORPUS_JSONL = Path(__file__).resolve().parents[1] / "data" / "processed" / "corpus.jsonl"


def corpus(limit: int) -> Iterator[Document]:
    """Stream the JSONL cache written by extract_corpus.py. Falls back to the
    tarball only if the cache is absent."""
    if not CORPUS_JSONL.exists():
        print("  no JSONL cache — falling back to tarball (slow)")
        n = 0
        for doc in load_directory():
            yield doc
            n += 1
        for doc in load_enron(limit=max(0, limit - n)):
            yield doc
        return

    import json
    with CORPUS_JSONL.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            yield Document(**json.loads(line))


def rows_for(doc: Document, chunks, vectors) -> list[dict]:
    year = _year(doc.created_at)
    out = []
    for chunk, vec in zip(chunks, vectors):
        out.append({
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "parent_id": chunk.parent_id,
            "ordinal": int(chunk.ordinal),
            "text": chunk.text,
            "vector": vec.tolist(),
            "title": doc.title or "",
            "author": doc.author or "",
            "department": doc.department or "General",
            "classification": doc.classification,
            "fmt": doc.fmt,
            "source": doc.source,
            "created_at": doc.created_at or "",
            "year": year,
            "page": int(chunk.page or 0),
            "custodian": doc.meta.get("custodian", "") or "",
            "thread_key": doc.meta.get("thread_key", "") or "",
            "recipients": doc.meta.get("recipients", "") or "",
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=DEFAULT_DOC_LIMIT)
    ap.add_argument("--smoke", action="store_true",
                    help="500-document dry run into the same tables")
    ap.add_argument("--reset", action="store_true", help="drop tables first")
    ap.add_argument("--no-index", action="store_true",
                    help="skip ANN/FTS index build at the end")
    args = ap.parse_args()

    limit = 500 if args.smoke else args.limit

    if args.reset:
        print("dropping existing tables")
        store.drop_all()
        if manifest.MANIFEST_DB.exists():
            manifest.MANIFEST_DB.unlink()

    manifest.init()
    done = manifest.indexed_ids()
    print(f"manifest: {len(done):,} documents already indexed")
    print(f"target:   {limit:,} documents\n")

    chunks_tbl = store.chunks_table()
    parents_tbl = store.parents_table()

    chunk_buf: list[dict] = []
    parent_buf: list[dict] = []
    record_buf: list[dict] = []

    seen = skipped = failed = 0
    total_chunks = 0
    t0 = time.time()

    def flush() -> None:
        nonlocal chunk_buf, parent_buf, record_buf, total_chunks
        if not chunk_buf:
            return
        chunks_tbl.add(chunk_buf)
        if parent_buf:
            parents_tbl.add(parent_buf)
        manifest.mark_indexed(record_buf)
        total_chunks += len(chunk_buf)
        elapsed = time.time() - t0
        rate = seen / elapsed if elapsed else 0
        print(f"  committed {seen:,} docs / {total_chunks:,} chunks "
              f"| {rate:.0f} docs/s | {elapsed/60:.1f} min")
        chunk_buf, parent_buf, record_buf = [], [], []

    pending_docs: list[tuple[Document, list, list]] = []

    def drain() -> None:
        """Embed the pending documents as one GPU batch."""
        nonlocal pending_docs
        if not pending_docs:
            return
        texts = [c.text for _, _, cs in pending_docs for c in cs]
        vectors = encode_passages(texts)
        cursor = 0
        for doc, parents, cs in pending_docs:
            vecs = vectors[cursor:cursor + len(cs)]
            cursor += len(cs)
            chunk_buf.extend(rows_for(doc, cs, vecs))
            parent_buf.extend({
                "parent_id": p.parent_id, "doc_id": p.doc_id,
                "ordinal": int(p.ordinal), "text": p.text,
            } for p in parents)
            record_buf.append({
                "doc_id": doc.doc_id, "source": doc.source, "fmt": doc.fmt,
                "title": doc.title, "author": doc.author,
                "department": doc.department, "created_at": doc.created_at,
                "n_chunks": len(cs), "n_chars": doc.n_chars,
            })
        pending_docs = []

    try:
        for doc in corpus(limit):
            if seen >= limit:
                break
            if doc.doc_id in done:
                skipped += 1
                continue

            try:
                parents, chunks = chunk_document(doc)
            except Exception as exc:
                manifest.mark_failed(doc.doc_id, doc.source, doc.fmt, repr(exc))
                failed += 1
                continue
            if not chunks:
                continue

            pending_docs.append((doc, parents, chunks))
            seen += 1

            if sum(len(c) for _, _, c in pending_docs) >= EMBED_BATCH * 4:
                drain()
            if len(chunk_buf) >= COMMIT_EVERY * 2:
                flush()

        drain()
        flush()

    except KeyboardInterrupt:
        print("\ninterrupted — flushing committed work")
        drain()
        flush()
        print("resume by re-running the same command")
        return

    dt = time.time() - t0
    print(f"\ningest complete in {dt/60:.1f} min")
    print(f"  indexed {seen:,} new  |  skipped {skipped:,}  |  failed {failed}")

    release()   # free VRAM before index build

    if not args.no_index:
        print("\nbuilding indices")
        store.build_indices()

    print("\nmanifest summary")
    for k, v in manifest.stats().items():
        print(f"  {k}: {v}")
    print(f"\nlance rows: {store.counts()}")
    print(f"finished {datetime.now(timezone.utc).isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()