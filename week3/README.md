# Enterprise Knowledge Intelligence Platform

**Week 3 — Production-Grade Retrieval-Augmented Generation**
Arsalan Ibrahim · Code Room Hub AI Internship · CRH-2026-AI-034

A hybrid-retrieval RAG platform over 100,000 documents with cross-encoder
reranking, per-sentence citation verification, cross-encoder grounding scores,
and role-based access control enforced at the query layer.

---

## What it does

| Requirement | Implementation |
|---|---|
| Index 100,000+ documents | 100,000 documents → 264,671 chunks → 136,197 parent windows in LanceDB |
| Multi-format ingestion | PDF, DOCX, HTML, CSV and email, one `Document` contract per loader |
| Semantic + keyword search | Dense (bge-small) and BM25 (Tantivy) fused by reciprocal rank |
| Automatic citations | `[n]` markers parsed, verified against real sources, invalid markers stripped |
| Access control by role | Six roles → `Filter` scope ANDed into every query, no bypass path |
| Multi-document reasoning | Parent-child retrieval; answers cite across separate documents |
| Conversation memory | Session store with LLM query rewriting for follow-ups |
| Analytics dashboard | Per-query telemetry in SQLite, aggregates served to the UI |
| REST API | FastAPI, 11 endpoints, OpenAPI docs at `/docs` |

Topics also implemented: multi-vector retrieval, parent-child retrieval,
self-query retrieval, context compression, reranking, metadata filtering,
citation generation, hallucination detection.

---

## Architecture

```
corpus.jsonl ─► chunker ─► bge-small (fp16) ─┐
                    │                        ├─► LanceDB
                    └─► parent windows ──────┘   (IVF_PQ + Tantivy FTS)
                                                       │
query ─► self-query split ─► ┌─ dense (cosine) ────┐   │
                             ├─ sparse (BM25) ─────┤◄──┘
                             └─ RRF fusion ────────┘
                                       ▼
                          bge-reranker-base (top-50 → top-8)
                                       ▼
                     context compression ─► Groq generation
                                       ▼
                  citation parse ─► cross-encoder grounding
```

**Why LanceDB.** Vectors, full-text index and metadata predicates live in one
embedded engine, so hybrid retrieval is one query rather than a fan-out and a
manual join. No Docker, no daemon, on-disk.

**Why the reranker doubles as the grounding scorer.** Scoring an answer
sentence against its cited chunk is the same pairwise-relevance problem the
cross-encoder was trained on. Reusing it removes a separate NLI model
dependency entirely.

---

## Measured results

**Index build** — 100,000 documents, 264,671 chunks, 0 failures, **11.5 minutes**
on an RTX 3050 8GB (144 docs/s sustained). Extraction to JSONL cache: 1.3 min.

**Retrieval latency** (100k corpus, warm):

| Stage | p50 |
|---|---|
| Hybrid retrieval | 34 ms |
| + cross-encoder rerank (50 candidates) | 307 ms |
| Full RAG answer including generation | ~2.0 s |

**Retrieval quality.** A 20-query weak-supervision gold set showed all
configurations saturating recall@10 at 1.0 — with 264k chunks, finding *a*
relevant chunk is trivial, so recall does not discriminate. nDCG@10 does:

| Config | nDCG@10 | p50 |
|---|---|---|
| Dense only | 0.9641 | 34 ms |
| Hybrid (RRF) | 0.9648 | 34 ms |
| Hybrid + rerank | **0.9846** | 307 ms |

**Rank displacement is the clearer signal.** On an exact-identifier query
(`NGPL Nicor Citygate`), reranking promoted chunks from fused ranks 48, 44 and
39 into positions 1, 5 and 3 — all eight top results were promoted. The
bi-encoder and cross-encoder orderings disagree substantially in the head,
which is exactly the case reranking exists to handle.

**Hybrid earns its place on exact identifiers.** Dense retrieval alone scatters
gas-hub settlement prices; adding BM25 pulls the correct price table to rank 1.
Asked for Transco Zone 3 and NGPL Mid-Continent settlements, the system
returned $1.4422 and $1.6769/mmBtu with a citation, read out of an unlabelled
numeric price block.

**RBAC changes answers, not just result counts.** The same question asked as
Executive and as Contractor produces different source sets and different
answers — the restricted role's scope filter is applied before ANN search, not
after.

---

## Limitations

Stated honestly rather than omitted.

- **Gold labels are term-presence heuristics**, not human relevance judgements.
  A production evaluation needs annotated query-document pairs. The eval
  saturates on recall as a result.
- **Confidence combines two independent signals, and both are needed.**
  Grounding alone (claim vs. cited chunk) reports high confidence on an
  out-of-corpus question when the model faithfully quotes an irrelevant
  document that retrieval scored near zero. Confidence is therefore the
  product of grounding and the best cited retrieval score. Separately,
  grounding under-reports on 2,000-character heterogeneous chunks — a correct
  claim scored against a whole market bulletin is swamped by surrounding text.
  Sentence-level evidence selection would fix the second issue and is a
  straightforward extension of the existing compression module.
- **Department labels are heuristic**, inferred from maildir folder names and
  subject lines, not ground truth. RBAC therefore demonstrates the mechanism
  correctly over approximate metadata.
- **Single-node, single-tenant, batch indexing.** No incremental ingest, no
  replication, no multi-user isolation beyond role scoping.
- **Reranking depth capped at 50 candidates** to hold interactive latency on
  consumer hardware.
- Corpus is the Enron email corpus (1999–2002); questions outside that domain
  correctly return an abstention.

---

## Running it

```powershell
cd D:\crh-ai-internship\week3
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

$env:HF_HOME = "D:\hf_cache"
hf download BAAI/bge-small-en-v1.5 --max-workers 1
hf download BAAI/bge-reranker-base --max-workers 1
```

Corpus (423 MB, resumable, never extracted — streamed from the tarball):

```powershell
curl.exe -L -C - --retry 10 -o data\raw\enron_mail.tar.gz `
  https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
```

Build:

```powershell
python scripts\make_multiformat.py      # PDF/DOCX/HTML/CSV corpus
python scripts\extract_corpus.py        # tarball -> JSONL cache (1.3 min)
python scripts\build_index.py --reset   # 100k docs -> LanceDB (11.5 min)
```

Serve:

```powershell
uvicorn api:app --port 8000
```

Open `http://127.0.0.1:8000`. API docs at `/docs`.

`GROQ_API_KEY` goes in `week3/.env` (gitignored).

---

## Verification

```powershell
python -m pytest tests\ -q          # 40 tests
python scripts\check_retrieval.py   # RBAC + format prefilter assertions
python scripts\check_rerank.py      # rank deltas
python scripts\check_rag.py         # end-to-end, three roles
python scripts\eval_retrieval.py    # metrics table
```

---

## Layout

```
ingest/      loaders, chunker, embedding, resumable manifest
retrieval/   store, dense, sparse, hybrid RRF, rerank, filters, self-query
rag/         pipeline, prompts, citations, grounding, compression, memory, llm
auth/        roles and scope filters
analytics/   query telemetry
scripts/     corpus prep, index build, evaluation, diagnostics
static/      frontend
tests/       40 tests
```

**Design notes.** The manifest makes ingest resumable — an interrupted build
resumes at the last commit. Gzip is not seekable, so the tarball is decoded
once into a JSONL cache; re-reading it per build cost 7 hours instead of 12
minutes. `build_where` is the single point where access control compiles to a
predicate, so no endpoint can forget to apply it.

## Design decisions worth noting

Week 2's provider interface and guardrail layer carry over unchanged. Model
fallback is built in from the start because Groq rate limits are per model, not
per key — a single-model client fails the demo the moment a quota trips.