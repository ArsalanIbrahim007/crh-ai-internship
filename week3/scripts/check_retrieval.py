"""Manual retrieval sanity checks. Run after any index rebuild."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval import hybrid
from retrieval.filters import Filter


def show(title: str, res: dict, n: int = 8) -> None:
    print(f"\n=== {title}")
    print(f"    {res['stats']}")
    for x in res["results"][:n]:
        text = x["text"][:70].replace("\n", " ")
        print(f"  {x['fused_rank']:2d} {x['retriever']:14s} "
              f"{x['department']:10s} {x['fmt']:5s} {text}")


def main() -> None:
    show("hybrid: natural gas pipeline capacity",
         hybrid.search("natural gas pipeline capacity"))

    show("hybrid: exact-term probe (sparse should carry this)",
         hybrid.search("NGPL Nicor Citygate"))

    res = hybrid.search("meeting schedule",
                        user_filter=Filter(departments=["Trading"]))
    show("filtered: departments=['Trading']", res)
    depts = sorted(set(x["department"] for x in res["results"]))
    print(f"\n  departments returned: {depts}")
    print("  RBAC PREFILTER:", "PASS" if depts in ([], ["Trading"]) else "FAIL")

    res = hybrid.search("cost savings", user_filter=Filter(formats=["pdf"]))
    fmts = sorted(set(x["fmt"] for x in res["results"]))
    print(f"\n  formats returned: {fmts}")
    print("  FORMAT FILTER:", "PASS" if fmts in ([], ["pdf"]) else "FAIL")


if __name__ == "__main__":
    main()