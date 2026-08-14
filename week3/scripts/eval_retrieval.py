"""Retrieval evaluation: recall@k, MRR, nDCG across four configurations.

Gold labels come from the corpus itself — for each query we mark the chunks
containing required terms as relevant. This is weak supervision, not human
judgement, and the README says so. It is still sufficient to answer the only
question that matters: does hybrid beat dense, and does reranking beat hybrid.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import EVAL
from retrieval import pipeline

# (query, terms that must all appear for a chunk to count as relevant)
GOLD = [
    ("why did the california energy crisis happen", ["california", "crisis"]),
    ("employee stock option vesting", ["stock option"]),
    ("NGPL Nicor Citygate natural gas prices", ["ngpl"]),
    ("bankruptcy filing chapter 11", ["bankruptcy"]),
    ("mark to market accounting treatment", ["mark", "market"]),
    ("special purpose entity off balance sheet", ["balance sheet"]),
    ("FERC regulatory approval pipeline", ["ferc"]),
    ("employee severance package layoffs", ["severance"]),
    ("credit rating downgrade agencies", ["rating"]),
    ("weather derivatives trading desk", ["weather"]),
    ("broadband services network capacity", ["broadband"]),
    ("india dabhol power project", ["dabhol"]),
    ("audit committee arthur andersen", ["andersen"]),
    ("wholesale electricity price caps", ["price cap"]),
    ("natural gas storage injection withdrawal", ["storage"]),
    ("risk management policy limits", ["risk management"]),
    ("confidential attorney client privileged", ["privileged"]),
    ("quarterly earnings release results", ["earnings"]),
    ("pipeline capacity firm transportation", ["capacity"]),
    ("environmental compliance emissions", ["emission"]),
]


def is_relevant(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return all(t in low for t in terms)


def dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg(rels: list[int]) -> float:
    ideal = dcg(sorted(rels, reverse=True))
    return dcg(rels) / ideal if ideal else 0.0


def evaluate(name: str, **kwargs) -> dict:
    recalls, rrs, ndcgs, latencies = [], [], [], []

    for query, terms in GOLD:
        t0 = time.perf_counter()
        res = pipeline.retrieve(query, top_k=10, **kwargs)
        latencies.append((time.perf_counter() - t0) * 1000)

        rels = [1 if is_relevant(r["text"], terms) else 0
                for r in res["results"]]
        recalls.append(1.0 if any(rels) else 0.0)
        rrs.append(1.0 / (rels.index(1) + 1) if 1 in rels else 0.0)
        ndcgs.append(ndcg(rels))

    n = len(GOLD)
    latencies.sort()
    return {
        "config": name,
        "queries": n,
        "recall@10": round(sum(recalls) / n, 4),
        "mrr@10": round(sum(rrs) / n, 4),
        "ndcg@10": round(sum(ndcgs) / n, 4),
        "latency_p50_ms": round(latencies[n // 2], 1),
        "latency_p95_ms": round(latencies[int(n * 0.95) - 1], 1),
    }


def main() -> None:
    configs = [
        ("dense only", dict(use_reranker=False, candidates=10)),
        ("hybrid (RRF)", dict(use_reranker=False, candidates=50)),
        ("hybrid + rerank", dict(use_reranker=True, candidates=50)),
    ]

    rows = []
    for name, kwargs in configs:
        print(f"running: {name}")
        rows.append(evaluate(name, **kwargs))

    header = f"{'config':18s} {'recall@10':>10s} {'mrr@10':>8s} {'ndcg@10':>8s} {'p50 ms':>8s} {'p95 ms':>8s}"
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['config']:18s} {r['recall@10']:10.4f} {r['mrr@10']:8.4f} "
              f"{r['ndcg@10']:8.4f} {r['latency_p50_ms']:8.1f} "
              f"{r['latency_p95_ms']:8.1f}")

    out = EVAL / "retrieval_eval.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()