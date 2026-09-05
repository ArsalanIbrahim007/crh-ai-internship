"""Central configuration. Every path, model name, and tunable constant lives here."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ============================================================
# PROJECT
# ============================================================

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
WORKSPACE_DIR = DATA_DIR / "workspace"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
MEMORY_DIR = DATA_DIR / "memory"
LOGS_DIR = DATA_DIR / "logs"
EVAL_DIR = ROOT / "results"

for _p in (DATA_DIR, WORKSPACE_DIR, CHECKPOINTS_DIR, MEMORY_DIR, LOGS_DIR, EVAL_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ============================================================
# DATABASE PATHS
# ============================================================

MEMORY_DB = MEMORY_DIR / "memory.sqlite"
CHECKPOINTS_DB = CHECKPOINTS_DIR / "checkpoints.sqlite"

# ============================================================
# MODELS (Groq-hosted, with fallback chain)
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen/qwen3.8-27b")
FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",
]

# ============================================================
# AGENT SYSTEM
# ============================================================

MAX_REFLECTION_RETRIES = 3          # QA <-> SWE fix loop
MAX_AGENT_TURNS = 15                # per-agent guardrail against infinite loops
AGENT_TEMPERATURE = 0.2             # low for deterministic tool use
PLANNING_TEMPERATURE = 0.4          # slightly higher for creative planning
RATE_LIMIT_DELAY_SECONDS = 65       # pause between agent nodes (Groq free-tier: 1000 OTPM)

# ============================================================
# SANDBOX
# ============================================================

SANDBOX_TIMEOUT_SECONDS = 30        # hard timeout for code / test execution
SANDBOX_MAX_OUTPUT_BYTES = 50_000   # cap stdout/stderr capture

# ============================================================
# SECURITY
# ============================================================

# AST-banned module/function calls in generated code
BANNED_MODULES = frozenset({
    "subprocess", "shutil", "socket", "http.server",
    "ftplib", "smtplib", "ctypes", "multiprocessing",
})

BANNED_CALLS = frozenset({
    "os.system", "os.popen", "os.exec", "os.execl", "os.execle",
    "os.execlp", "os.execv", "os.execve", "os.execvp", "os.execvpe",
    "os.spawn", "os.spawnl", "os.spawnle", "eval", "exec", "__import__",
})

# ============================================================
# TOOLS
# ============================================================

SEARCH_MAX_RESULTS = 5

# ============================================================
# WEB UI
# ============================================================

API_HOST = "0.0.0.0"
API_PORT = 8000
