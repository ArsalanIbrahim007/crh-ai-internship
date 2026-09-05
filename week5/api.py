"""FastAPI backend for the Autonomous Business Operations Platform.

Endpoints:
  POST /api/run           — Start a new workflow (returns thread_id)
  GET  /api/state/{id}    — Get current state of a workflow
  GET  /api/health        — Test Groq API connectivity
  GET  /api/workspace     — List workspace files
  GET  /api/workspace/{p} — Read a workspace file
  GET  /                  — Serve the dashboard
"""

from __future__ import annotations

import json
import asyncio
import logging
import traceback
import uuid
import concurrent.futures
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import WORKSPACE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("autonomops")

app = FastAPI(title="Autonomous Business Operations Platform", version="1.0.0")

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── In-memory workflow tracker ──────────────────────────────────
# Maps thread_id → {"status": ..., "error": ..., "state": ...}
_workflows: dict[str, dict] = {}


class InitiativeRequest(BaseModel):
    initiative: str


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return index.read_text(encoding="utf-8")
    return "<h1>Dashboard not found. Place index.html in static/</h1>"


@app.get("/api/health")
async def health_check():
    """Test Groq API connectivity with a tiny request."""
    from providers.groq_provider import GroqProvider

    try:
        provider = GroqProvider()
        resp = provider.chat(
            messages=[{"role": "user", "content": "Reply with only the word OK."}],
            max_tokens=10,
        )
        return {
            "status": "ok",
            "model_used": resp.model_used,
            "response": resp.text[:50],
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": str(e)},
        )


@app.post("/api/run")
async def run_workflow(req: InitiativeRequest):
    """Start a new workflow and return the thread_id immediately."""
    thread_id = str(uuid.uuid4())

    _workflows[thread_id] = {
        "status": "running",
        "error": None,
        "state": {
            "initiative": req.initiative,
            "current_phase": "started",
            "messages": [],
        },
    }

    log.info(f"Starting workflow {thread_id[:8]} for: {req.initiative[:60]}...")
    asyncio.ensure_future(_run_in_background(req.initiative, thread_id))

    return {"thread_id": thread_id, "status": "started"}


async def _run_in_background(initiative: str, thread_id: str):
    """Run the orchestrator in a thread so it doesn't block the event loop."""
    from orchestration.orchestrator import Orchestrator

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            orch = Orchestrator()
            result = await loop.run_in_executor(
                pool,
                lambda: orch.run(initiative, thread_id=thread_id),
            )
            _workflows[thread_id]["status"] = "complete"
            _workflows[thread_id]["state"] = result
            log.info(f"Workflow {thread_id[:8]} completed successfully.")
            orch.close()
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            log.error(f"Workflow {thread_id[:8]} FAILED: {error_msg}")
            log.error(traceback.format_exc())
            _workflows[thread_id]["status"] = "error"
            _workflows[thread_id]["error"] = error_msg
            _workflows[thread_id]["state"]["current_phase"] = "error"
            # Add error to messages so the UI shows it
            _workflows[thread_id]["state"]["messages"].append({
                "agent": "system",
                "content": f"❌ Workflow failed: {error_msg}",
                "turns": 0,
                "model_used": "",
                "tool_calls": [],
            })


@app.get("/api/state/{thread_id}")
async def get_state(thread_id: str):
    """Get the current state of a workflow."""
    # Check in-memory tracker first
    if thread_id in _workflows:
        wf = _workflows[thread_id]
        state = dict(wf["state"])
        state["workflow_status"] = wf["status"]
        state["workflow_error"] = wf["error"]
        return _serialize_state(state)

    # Fall back to checkpointer
    from orchestration.orchestrator import Orchestrator
    orch = Orchestrator()
    try:
        state = orch.get_state(thread_id)
        if state is None:
            return JSONResponse(status_code=404, content={"error": "Thread not found"})
        return _serialize_state(state)
    finally:
        orch.close()


@app.post("/api/run-sync")
async def run_sync(req: InitiativeRequest):
    """Run a workflow synchronously and return the full result.

    Useful for testing. For production, use /api/run + polling /api/state.
    """
    from orchestration.orchestrator import Orchestrator

    orch = Orchestrator()
    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool,
                lambda: orch.run(req.initiative),
            )
        return _serialize_state(result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()},
        )
    finally:
        orch.close()


@app.get("/api/workspace")
async def list_workspace():
    """List files in the workspace."""
    files = []
    if WORKSPACE_DIR.exists():
        for p in WORKSPACE_DIR.rglob("*"):
            if p.is_file():
                files.append({
                    "path": str(p.relative_to(WORKSPACE_DIR)),
                    "size": p.stat().st_size,
                })
    return {"files": files}


@app.get("/api/workspace/{path:path}")
async def read_workspace_file(path: str):
    """Read a file from the workspace."""
    target = (WORKSPACE_DIR / path).resolve()
    if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
        return JSONResponse(status_code=403, content={"error": "Path escape"})
    if not target.exists():
        return JSONResponse(status_code=404, content={"error": "File not found"})
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content}


def _serialize_state(state: dict) -> dict:
    """Make state JSON-serializable."""
    result = {}
    for k, v in state.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            result[k] = v
        elif isinstance(v, dict):
            result[k] = {str(dk): str(dv)[:5000] for dk, dv in v.items()}
        elif isinstance(v, list):
            result[k] = [
                _serialize_message(item) if isinstance(item, dict) else str(item)
                for item in v
            ]
        else:
            result[k] = str(v)
    return result


def _serialize_message(msg: dict) -> dict:
    return {
        "agent": msg.get("agent", ""),
        "content": (msg.get("content", "") or "")[:3000],
        "turns": msg.get("turns", 0),
        "model_used": msg.get("model_used", ""),
        "tool_calls_count": len(msg.get("tool_calls", [])),
    }
