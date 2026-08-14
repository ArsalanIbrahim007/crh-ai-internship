"""Show what reranking actually changes. Rank deltas are the evidence."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval import pipeline

QUERIES = [
    "why did the california energy crisis happen",
    "employee stock option vesting schedule",
    "NGPL Nicor Citygate",
]


def main() -> None:
    for q in QUERIES:
        res = pipeline.retrieve(q, top_k=8)
        s = res["stats"]
        print(f"\n=== {q}")
        print(f"    fused={s['fused']} overlap={s['overlap']} "
              f"rerank={s['rerank'].get('latency_ms')}ms "
              f"total={s['total_latency_ms']}ms "
              f"promoted={s['rerank'].get('promoted')}")
        for r in res["results"]:
            arrow = ("+" if r["rank_delta"] > 0 else
                     " " if r["rank_delta"] == 0 else "-")
            text = r["text"][:64].replace("\n", " ")
            print(f"  {r['final_rank']:2d} {arrow}{abs(r['rank_delta']):<3d} "
                  f"score={r['rerank_score']:.3f} {r['department']:10s} "
                  f"{r['fmt']:5s} {text}")


if __name__ == "__main__":
    main()