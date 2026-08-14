"""Central configuration. Every path and knob lives here."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# --- paths -------------------------------------------------------------
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
INDEX = DATA / "index"
LOGS = DATA / "logs"
EVAL = DATA / "eval"

for _p in (RAW, PROCESSED, INDEX, LOGS, EVAL):
    _p.mkdir(parents=True, exist_ok=True)

ENRON_TARBALL = RAW / "enron_mail.tar.gz"
MULTIFORMAT_DIR = RAW / "multiformat"
MANIFEST_DB = PROCESSED / "manifest.sqlite"

LANCE_URI = str(INDEX / "kip.lance")
CHUNK_TABLE = "chunks"
PARENT_TABLE = "parents"

# --- models ------------------------------------------------------------
os.environ.setdefault("HF_HOME", r"D:\hf_cache")
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
RERANK_MODEL = "BAAI/bge-reranker-base"

# bge models want this prefix on the *query* side only.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

EMBED_BATCH = 128
RERANK_BATCH = 32

# --- chunking ----------------------------------------------------------
CHUNK_TOKENS = 320
CHUNK_OVERLAP = 64
MIN_CHUNK_CHARS = 80

# --- retrieval ---------------------------------------------------------
DENSE_K = 50
SPARSE_K = 50
RRF_K = 60          # smoothing constant in reciprocal-rank fusion
FUSED_K = 50        # candidates handed to the reranker
FINAL_K = 8         # chunks handed to the LLM

GROUNDING_THRESHOLD = 0.15   # reranker score below this => flagged sentence

# --- generation --------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# --- ingest limits -----------------------------------------------------
DEFAULT_DOC_LIMIT = 100_000
MULTIFORMAT_SLICE = 600

DEVICE = "cuda"