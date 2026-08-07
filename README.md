# Code Room Hub — AI Internship

**Arsalan Ibrahim** · Internship ID: CRH-2026-AI-034
6-Week Artificial Intelligence Internship, 16 July – 5 September 2026 · Remote

Weekly tasks and capstone work. All experiments run locally on an RTX 3050 (8 GB) unless a
week's README says otherwise.

---

## Contents

| | Topic | Status |
|---|---|---|
| [Week 1](week1/) | Modern LLMs and transformer architecture | Complete |
| Week 2 | Advanced prompt engineering and LLM applications | In progress |

**Capstone:** AI Business Intelligence Copilot — SQL generation, KPI analysis, executive
reporting and insight generation over an enterprise data warehouse. Separate repository.

---

## Week 1 — Modern LLMs and Transformer Architecture

A transformer decoder block built from scratch in PyTorch, six open models benchmarked on local
hardware, and a dashboard comparing them across response quality, inference speed, GPU memory,
context length, latency and cost.

**Selected findings:**

- **Advertised context is not usable context.** Phi-3.5-mini quotes a 131,072 token window and
  reaches 12.3% of it on an 8 GB card, because it is the only model tested without grouped query
  attention. Its KV cache would need 51 GB at full context; Llama-3.2-1B needs 4.29 GB for the
  same advertised figure.
- **Parameter count does not predict inference speed.** Correlation of −0.34 against −0.66 for
  layer count. Phi-3.5-mini is 2.5× the size of Qwen2.5-1.5B and 24% faster.
- **Quantization is a memory technique, not a speed technique.** 4-bit NF4 saved 62.7% memory and
  cost 19.9% decode speed.
- **Run-to-run variance reaches 10%** and reordered part of the results table between two runs, so
  differences below that threshold are not meaningful.

Full write-up, method and limitations: [week1/README.md](week1/README.md)

---

## Repository conventions

- Model weights, caches, databases and generated output are gitignored — they are large and
  reproducible.
- Secrets live in `.env`, which is never committed. Each week that needs keys ships an
  `.env.example` with blank values.
- Every week is self-contained: its own README, its own dependency list, its own reproduction
  steps.
