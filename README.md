# Code Room Hub — AI Internship

**Arsalan Ibrahim · Internship ID: CRH-2026-AI-034**
6-Week Artificial Intelligence Internship, 16 July – 5 September 2026 · Remote

Weekly tasks and capstone work. All experiments run locally on an RTX 3050 (8 GB) unless a week's README says otherwise.

## Contents

| Topic | Status |
|---|---|
| Week 1 | Modern LLMs and transformer architecture | Complete |
| Week 2 | Advanced prompt engineering and LLM applications | Complete |
| Week 3 | Production-grade Retrieval-Augmented Generation | Complete |

**Capstone: AI Business Intelligence Copilot** — SQL generation, KPI analysis, executive reporting and insight generation over an enterprise data warehouse. Separate repository.

---

## Week 1 — Modern LLMs and Transformer Architecture

A transformer decoder block built from scratch in PyTorch, six open models benchmarked on local hardware, and a dashboard comparing them across response quality, inference speed, GPU memory, context length, latency and cost.

**Selected findings:**

- **Advertised context is not usable context.** Phi-3.5-mini quotes a 131,072 token window and reaches 12.3% of it on an 8 GB card, because it is the only model tested without grouped query attention. Its KV cache would need 51 GB at full context; Llama-3.2-1B needs 4.29 GB for the same advertised figure.
- **Parameter count does not predict inference speed.** Correlation of −0.34 against −0.66 for layer count. Phi-3.5-mini is 2.5× the size of Qwen2.5-1.5B and 24% faster.
- **Quantization is a memory technique, not a speed technique.** 4-bit NF4 saved 62.7% memory and cost 19.9% decode speed.
- **Run-to-run variance reaches 10%** and reordered part of the results table between two runs, so differences below that threshold are not meaningful.

Full write-up, method and limitations: `week1/README.md`

---

## Week 2 — Advanced Prompt Engineering and LLM Applications

Ledger — an AI copilot built on Groq-hosted models with tool calling, layered guardrails, and a provenance rail that surfaces the SQL behind every response. FastAPI backend, custom frontend.

**Selected features:**

- **Tool calling** across SQL query, web search, email drafting and calendar scheduling, with the model selecting and sequencing tools per request.
- **Layered guardrails** — Meta Prompt Guard 2 for prompt-injection detection, plus a pattern-rule layer, applied before and after generation.
- **Provenance rail** — every data-backed answer shows the exact SQL that produced it, so a claim can be traced to its source rather than trusted blind.
- **Model fallback** built in from the start, because Groq rate limits are per model, not per key.

Full write-up, method and limitations: `week2/README.md`

---

## Week 3 — Production-Grade Retrieval-Augmented Generation

The Enterprise Knowledge Intelligence Platform — a hybrid-retrieval RAG system over 100,000 documents (264,671 chunks) with cross-encoder reranking, per-sentence citation verification, cross-encoder grounding scores, and role-based access control enforced at the query layer.

**Selected findings:**

- **Reranking disagrees with retrieval in the head, which is the point.** On an exact-identifier query, the cross-encoder promoted chunks from fused ranks 48, 44 and 39 into positions 1, 5 and 3 — all eight top results were promoted. The bi-encoder and cross-encoder orderings diverge exactly where it matters.
- **Recall saturates; nDCG discriminates.** Over 264k chunks, finding *a* relevant chunk is trivial, so recall@10 hit 1.0 for every configuration. nDCG@10 separated them: hybrid+rerank 0.9846 against 0.9648 for hybrid and 0.9641 for dense alone.
- **Confidence needs two signals, not one.** Grounding alone (claim vs. cited chunk) reports high confidence on an out-of-corpus question when the model faithfully quotes an irrelevant document. Confidence is therefore the product of grounding and the best cited retrieval score — an out-of-corpus question that would otherwise score 0.998 correctly drops to 0.003 and abstains.
- **Grounding under-reports on dense chunks.** A correct one-line claim scored against a 2,000-character price table is swamped by surrounding text and scores below 0.05; prose answers score 0.85–0.99. Documented as a calibration limitation with a known fix.

Also implemented: multi-format ingestion (PDF, DOCX, HTML, CSV, email), self-query retrieval, context compression, parent-child retrieval, conversation memory, live document upload and delete with immediate re-indexing, an analytics dashboard, a FastAPI REST API, and 40 tests. Index build: 100,000 documents in 11.5 minutes on the RTX 3050.

Full write-up, method and limitations: `week3/README.md`

---

## Repository conventions

- Model weights, caches, databases and generated output are gitignored — they are large and reproducible.
- Secrets live in `.env`, which is never committed. Each week that needs keys ships an `.env.example` with blank values.
- Every week is self-contained: its own README, its own dependency list, its own reproduction steps.