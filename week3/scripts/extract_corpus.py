"""Tarball -> JSONL, once.

Gzip is not seekable, so every pass over the archive pays full decompression.
The index build should never touch the tarball more than once. This script
writes a flat JSONL cache that build_index streams at disk speed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DEFAULT_DOC_LIMIT, PROCESSED
from ingest.loaders import load_directory, load_enron

OUT = PROCESSED / "corpus.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=DEFAULT_DOC_LIMIT)
    args = ap.parse_args()

    t0 = time.time()
    n = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for doc in load_directory():
            fh.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")
            n += 1
        print(f"multi-format: {n}")

        for doc in load_enron(limit=max(0, args.limit - n)):
            fh.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")
            n += 1
            if n % 10_000 == 0:
                print(f"  {n:,} docs | {(time.time()-t0)/60:.1f} min")

    mb = OUT.stat().st_size / 1e6
    print(f"\nwrote {n:,} documents to {OUT} ({mb:.0f} MB) "
          f"in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()