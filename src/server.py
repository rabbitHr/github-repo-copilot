"""
DevMind API Server
Exposes REST endpoints for indexing a codebase and asking questions.
"""

import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from indexer import index_codebase
from agent import RepoMindAgent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="DevMind API",
    description="Codebase Q&A powered by Endee vector search + Claude LLM",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve UI and static assets from repo root when running inside src/
app.mount("/static", StaticFiles(directory="..", html=False), name="static")

# Lazy singleton — only created on first /ask request
_agent: RepoMindAgent | None = None

def get_agent() -> RepoMindAgent:
    global _agent
    if _agent is None:
        _agent = RepoMindAgent()
    return _agent


# ── Models ────────────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    repo_path: str

class IndexResponse(BaseModel):
    status: str
    chunks_indexed: int | None = None

class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    api_key: str | None = None

class Source(BaseModel):
    file: str
    lines: str
    similarity: float

class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "RepoMind"}


@app.get("/")
def root():
    return FileResponse("../ui.html")


@app.get("/ui.html")
def ui_html():
    return FileResponse("../ui.html")


@app.post("/index", response_model=IndexResponse)
def index(req: IndexRequest):
    """
    Index all source files under `repo_path` into Endee.
    This is a synchronous endpoint — for large repos use /index/async.
    """
    try:
        chunks = index_codebase(req.repo_path)
        return IndexResponse(status="success", chunks_indexed=chunks)
    except Exception as e:
        log.exception("Indexing failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    """
    Answer a natural-language question about the indexed codebase.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        agent = get_agent()
        if req.api_key:
            agent.set_api_key(req.api_key)
        result = agent.answer(req.question, top_k=req.top_k)
        return AskResponse(**result)
    except Exception as e:
        log.exception("Agent failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
