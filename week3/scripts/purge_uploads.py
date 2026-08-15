"""Remove uploaded documents from disk, index and manifest.

Uploads are the only mutable part of the corpus, so this is the only place
deletion is needed. Run with --all to clear every upload, or --doc-id to
remove one.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ROOT
from ingest import manifest
from retrieval.store import chunks_table, parents_table

UPLOADS = ROOT / "data" / "raw" / "uploads"


def uploaded_rows() -> list[dict]:
    with manifest.connect() as conn:
        rows = conn.execute(
            "SELECT doc_id, title, source, n_chunks FROM documents "
            "WHERE source LIKE '%uploads%'"
        ).fetchall()
    return [dict(r) for r in rows]


def purge(doc_ids: list[str]) -> None:
    if not doc_ids:
        print("nothing to purge")
        return

    quoted = ", ".join("'" + d.replace("'", "") + "'" for d in doc_ids)

    chunks_table().delete(f"doc_id IN ({quoted})")
    parents_table().delete(f"doc_id IN ({quoted})")

    with manifest.connect() as conn:
        conn.execute(f"DELETE FROM documents WHERE doc_id IN ({quoted})")

    print(f"removed {len(doc_ids)} document(s) from index and manifest")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="purge every upload")
    ap.add_argument("--doc-id", help="purge one document")
    ap.add_argument("--list", action="store_true", help="show uploads only")
    args = ap.parse_args()

    rows = uploaded_rows()

    if args.list or not (args.all or args.doc_id):
        if not rows:
            print("no uploaded documents")
        for r in rows:
            print(f"  {r['doc_id']}  {r['n_chunks']:3d} chunks  "
                  f"{(r['title'] or '')[:50]}  {r['source']}")
        return

    targets = [r for r in rows if args.all or r["doc_id"] == args.doc_id]
    purge([r["doc_id"] for r in targets])

    for r in targets:
        p = Path(r["source"])
        if p.exists() and UPLOADS in p.parents:
            p.unlink()
            print(f"deleted file {p.name}")

    print(f"\nremaining index rows: {chunks_table().count_rows():,}")


if __name__ == "__main__":
    main()