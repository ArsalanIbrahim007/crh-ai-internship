"""FastAPI service for the Enterprise Knowledge Intelligence Platform.

Models are warmed at startup so the first user request does not pay the 16
second load. RBAC scope is derived server-side from the role header and is
never accepted from the client body.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from analytics import store as analytics
from auth import roles
from config import FINAL_K, FUSED_K, ROOT
from ingest import manifest
from rag import llm, memory, pipeline as rag_pipeline
from retrieval import pipeline as retrieval_pipeline, selfquery
from retrieval.filters import Filter
from retrieval.store import counts

STATIC = ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    analytics.init()
    manifest.init()
    # Warm both models: first request otherwise pays ~16s of load time.
    try:
        from ingest.embed import encode_query
        from retrieval.rerank import score_pairs
        encode_query("warmup")
        score_pairs("warmup", ["warmup passage"])
        print("models warm")
    except Exception as exc:
        print(f"warmup failed (non-fatal): {exc}")
    yield


app = FastAPI(title="Enterprise Knowledge Intelligence Platform",
              version="1.0.0", lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=FINAL_K, ge=1, le=25)
    candidates: int = Field(default=FUSED_K, ge=5, le=100)
    use_reranker: bool = True
    departments: list[str] = []
    formats: list[str] = []
    year_from: int | None = None
    year_to: int | None = None


class AskRequest(SearchRequest):
    session_id: str | None = None
    model: str | None = None
    use_compression: bool = True
    use_selfquery: bool = False


def user_filter_from(req: SearchRequest) -> Filter:
    return Filter(departments=req.departments, formats=req.formats,
                  year_from=req.year_from, year_to=req.year_to)


def role_of(x_role: str | None) -> str:
    return roles.get(x_role).name


@app.get("/api/health")
def health():
    return {"status": "ok", "index": counts(),
            "models": llm.available_models()}


@app.get("/api/roles")
def role_catalogue():
    return {"roles": roles.catalogue(), "default": roles.DEFAULT_ROLE}


@app.get("/api/corpus")
def corpus_stats():
    return {"manifest": manifest.stats(), "index": counts()}


@app.post("/api/search")
def search(req: SearchRequest, x_role: str | None = Header(default=None)):
    role = role_of(x_role)
    res = retrieval_pipeline.retrieve(
        req.query, top_k=req.top_k, candidates=req.candidates,
        user_filter=user_filter_from(req), scope=roles.scope_for(role),
        use_reranker=req.use_reranker,
    )
    return {
        "role": role,
        "results": [{
            "chunk_id": r["chunk_id"], "doc_id": r["doc_id"],
            "title": r.get("title"), "department": r.get("department"),
            "fmt": r.get("fmt"), "author": r.get("author"),
            "created_at": r.get("created_at"), "page": r.get("page"),
            "text": r["text"],
            "score": round(r.get("rerank_score", 0.0), 4),
            "retriever": r.get("retriever"),
            "rank_delta": r.get("rank_delta", 0),
        } for r in res["results"]],
        "stats": res["stats"],
    }


@app.post("/api/ask")
def ask(req: AskRequest, x_role: str | None = Header(default=None)):
    role = role_of(x_role)
    question = req.query
    ufilter = user_filter_from(req)
    extracted = {}

    if req.use_selfquery:
        sq = selfquery.parse_query(question)
        question = sq["query"]
        ufilter = ufilter.merge(sq["filter"])
        extracted = sq["extracted"]

    try:
        res = rag_pipeline.answer(
            question if req.use_selfquery else req.query,
            role_scope=roles.scope_for(role),
            user_filter=ufilter,
            session_id=req.session_id,
            model=req.model,
            top_k=req.top_k,
            candidates=req.candidates,
            use_reranker=req.use_reranker,
            use_compression=req.use_compression,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    res["role"] = role
    res["selfquery"] = extracted
    analytics.record(res, role, req.session_id,
                     {"departments": req.departments, "formats": req.formats})
    return res


@app.get("/api/analytics")
def analytics_summary():
    return analytics.summary()


@app.get("/api/sessions")
def sessions():
    return {"sessions": memory.list_sessions()}


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str):
    return {"session_id": session_id, "turns": memory.load(session_id)}


@app.delete("/api/sessions/{session_id}")
def session_delete(session_id: str):
    memory.clear(session_id)
    return {"deleted": session_id}


@app.post("/api/sessions")
def session_new():
    return {"session_id": memory.new_session()}


@app.get("/api/document/{doc_id}")
def document(doc_id: str):
    from retrieval.store import chunks_table
    safe = "".join(c for c in doc_id if c.isalnum())[:40]
    rows = (chunks_table().search()
            .where(f"doc_id = '{safe}'").limit(200).to_list())
    if not rows:
        raise HTTPException(status_code=404, detail="document not found")
    rows.sort(key=lambda r: r.get("ordinal", 0))
    head = rows[0]
    return {
        "doc_id": doc_id,
        "title": head.get("title"), "author": head.get("author"),
        "department": head.get("department"), "fmt": head.get("fmt"),
        "source": head.get("source"), "created_at": head.get("created_at"),
        "classification": head.get("classification"),
        "chunks": [{"ordinal": r.get("ordinal"), "text": r["text"],
                    "page": r.get("page")} for r in rows],
    }


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    f = STATIC / "index.html"
    if not f.exists():
        return JSONResponse({"error": "frontend not built"}, status_code=404)
    return FileResponse(str(f))