"""Hallucination detection by cross-encoder entailment scoring.

Each answer sentence is scored against the source it cites, using the same
reranker that ordered the candidates. Relevance between a claim and its
evidence is the same pairwise problem the cross-encoder was trained on, so no
separate NLI model is required — one fewer download, one fewer dependency.

A low score means the sentence is not supported by what it points at. That is
flagged, not deleted: the user sees the claim and the fact that it is weakly
grounded.
"""
from __future__ import annotations

from config import GROUNDING_THRESHOLD
from retrieval.rerank import normalise, score_pairs


def score_answer(parsed: dict, chunks: list[dict]) -> dict:
    """Attach a grounding score to every sentence in a parsed answer."""
    sentences = parsed["sentences"]
    if not sentences:
        return parsed

    by_n = {i: c for i, c in enumerate(chunks, 1)}

    pairs: list[tuple[int, str, str]] = []
    for idx, sent in enumerate(sentences):
        for n in sent["citations"]:
            chunk = by_n.get(n)
            if chunk:
                evidence = chunk.get("parent_text") or chunk["text"]
                pairs.append((idx, sent["text"], evidence[:2000]))

    if pairs:
        # one batched forward pass for the whole answer
        raw = score_pairs("", [""] * 0)  # warm path no-op for empty input
        raw = []
        queries = [p[1] for p in pairs]
        evidence = [p[2] for p in pairs]
        raw = _score_many(queries, evidence)
        probs = normalise(raw)

        best: dict[int, float] = {}
        for (idx, _, _), p in zip(pairs, probs):
            best[idx] = max(best.get(idx, 0.0), p)
    else:
        best = {}

    flagged = 0
    for idx, sent in enumerate(sentences):
        if sent["uncited"]:
            sent["grounding"] = None
            sent["flagged"] = True
            flagged += 1
            continue
        score = best.get(idx, 0.0)
        sent["grounding"] = round(score, 4)
        sent["flagged"] = score < GROUNDING_THRESHOLD
        if sent["flagged"]:
            flagged += 1

    scored = [s["grounding"] for s in sentences if s["grounding"] is not None]
    confidence = sum(scored) / len(scored) if scored else 0.0

    parsed["stats"].update({
        "flagged_sentences": flagged,
        "grounding_threshold": GROUNDING_THRESHOLD,
        "confidence": round(confidence, 4),
       "verdict": _verdict(confidence, parsed["stats"]["citation_coverage"],
                            parsed["answer"]),
    })
    return parsed


def _score_many(claims: list[str], evidence: list[str]) -> list[float]:
    """Cross-encoder over (claim, evidence) pairs, one batch."""
    from retrieval.rerank import get_model
    import torch

    tokenizer, model, device = get_model()
    out: list[float] = []
    batch = 16
    with torch.inference_mode():
        for i in range(0, len(claims), batch):
            enc = tokenizer(
                claims[i:i + batch], evidence[i:i + batch],
                padding=True, truncation=True, max_length=512,
                return_tensors="pt",
            ).to(device)
            logits = model(**enc).logits.view(-1).float()
            out.extend(logits.cpu().tolist())
    return out


NO_SUPPORT = ("do not contain", "does not contain", "no information",
              "not contain enough")


def _verdict(confidence: float, coverage: float,
             answer: str = "") -> str:
    if any(p in answer.lower() for p in NO_SUPPORT):
        return "abstained — no supporting sources"
    if coverage < 0.5:
        return "low — many claims uncited"
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "moderate"
    return "low — weak support in cited sources"