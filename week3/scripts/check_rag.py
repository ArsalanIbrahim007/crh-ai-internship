"""End-to-end RAG smoke test with RBAC contrast."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth import roles
from rag import pipeline


def show(res: dict) -> None:
    s = res["stats"]
    print(f"\nmodel={res['model']} conf={s['confidence']} "
          f"verdict={s['verdict']}")
    print(f"coverage={s['citation_coverage']} sources={s['sources_used']}"
          f"/{s['sources_offered']} flagged={s['flagged_sentences']}")
    print(f"timings={s['timings_ms']}")
    print()
    for sent in res["sentences"]:
        mark = "!" if sent["flagged"] else " "
        g = sent["grounding"]
        print(f" {mark} [{g if g is not None else '  -- '}] {sent['text']}")
    print("\n sources:")
    for src in res["sources"]:
        print(f"  [{src['n']}] {src['department']:10s} {src['fmt']:5s} "
              f"{src['title'][:56]}")


def main() -> None:
    q = "What caused the California energy crisis?"

    print("=" * 70)
    print(f"EXECUTIVE — {q}")
    show(pipeline.answer(q, role_scope=roles.scope_for("executive")))

    print("\n" + "=" * 70)
    print(f"CONTRACTOR (restricted role) — {q}")
    show(pipeline.answer(q, role_scope=roles.scope_for("contractor")))

    print("\n" + "=" * 70)
    print("REFUSAL TEST — question with no support in corpus")
    show(pipeline.answer("What is the melting point of tungsten?",
                         role_scope=roles.scope_for("executive")))


if __name__ == "__main__":
    main()