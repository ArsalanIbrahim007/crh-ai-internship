"""Show which rule fires for mislabelled documents."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.loaders import DEPT_RULES
from retrieval.store import chunks_table


def which_rule(*signals: str) -> str:
    blob = " ".join(s for s in signals if s)
    for pattern, dept in DEPT_RULES:
        m = pattern.search(blob)
        if m:
            return f"{dept} <- matched {m.group(0)!r} in {pattern.pattern[:40]}"
    return "General"


def main() -> None:
    rows = chunks_table().search().where("department = 'HR'").limit(400).to_list()
    print(f"HR-labelled chunks sampled: {len(rows)}\n")

    seen = set()
    for r in rows:
        if r["doc_id"] in seen:
            continue
        seen.add(r["doc_id"])
        stem = Path(r["source"]).stem
        verdict = which_rule(stem, r["title"])
        print(f"  {verdict}")
        print(f"     stem={stem[:70]}")
        if len(seen) >= 20:
            break

    print("\ncorpus-wide department counts:")
    all_rows = chunks_table().search().limit(20000).to_list()
    for dept, n in Counter(r["department"] for r in all_rows).most_common():
        print(f"  {dept:12s} {n:6,}")


if __name__ == "__main__":
    main()