"""
FastAPI service + web dashboard for the multi-agent content pipeline.

Endpoints:
  GET  /                  -> the web UI dashboard
  GET  /health            -> liveness, provider, model, whether a key is configured
  POST /generate          -> run the full pipeline synchronously, return result
  POST /generate/async    -> kick off a background run, return a run_id
  GET  /runs/{run_id}      -> fetch a previously completed run
  GET  /stream            -> Server-Sent Events: agents reporting progress live

This mirrors exposing an agent workflow behind a webhook in n8n/Make, but as a
self-contained, testable service with a real browser interface.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import uuid
from typing import Dict, Optional

# Load .env if present (keys never hardcoded in source).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from .llm import LLMClient
from .orchestrator import ContentPipeline

app = FastAPI(title="AI Multi-Agent Content Pipeline", version="2.0.0")

_llm = LLMClient()
_pipeline = ContentPipeline(_llm)

# Simple in-memory run store (swap for Postgres/Redis in production).
_runs: Dict[str, dict] = {}
_runs_lock = threading.Lock()

_UI_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, examples=["AI agents for small business automation"])
    audience: str = "general business readers"
    goal: str = "educate and drive engagement"
    tone: str = "clear and professional"
    words: int = Field(800, ge=200, le=3000)
    publish: bool = True


@app.get("/", response_class=HTMLResponse)
def index():
    with open(_UI_PATH, "r", encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": _llm.provider,
        "model": _llm.model,
        "llm_live": _llm.is_live,
    }


@app.post("/generate")
def generate(req: GenerateRequest):
    result = _pipeline.run(
        topic=req.topic, audience=req.audience, goal=req.goal,
        tone=req.tone, words=req.words, publish=req.publish,
    )
    payload = result.to_dict()
    with _runs_lock:
        _runs[result.run_id] = payload
    return payload


@app.post("/generate/async")
def generate_async(req: GenerateRequest, background_tasks: BackgroundTasks):
    run_id = uuid.uuid4().hex[:12]
    with _runs_lock:
        _runs[run_id] = {"run_id": run_id, "status": "running", "topic": req.topic}

    def _job():
        result = _pipeline.run(
            topic=req.topic, audience=req.audience, goal=req.goal,
            tone=req.tone, words=req.words, publish=req.publish,
        )
        payload = result.to_dict()
        payload["status"] = "done"
        with _runs_lock:
            _runs[run_id] = payload

    background_tasks.add_task(_job)
    return {"run_id": run_id, "status": "running"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    with _runs_lock:
        run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/stream")
def stream(topic: str, words: int = 800, tone: str = "clear and professional",
           audience: str = "general business readers", goal: str = "educate and drive engagement"):
    """
    Run the pipeline and stream per-stage events as SSE so the web UI can light
    up each agent as it finishes. Emits: start, stage, done events.
    """
    events: "queue.Queue" = queue.Queue()

    def _on_stage(name, info):
        events.put(("stage", {"name": name, **info}))

    def _job():
        try:
            events.put(("start", {"topic": topic, "live": _llm.is_live,
                                  "provider": _llm.provider, "model": _llm.model}))
            result = _pipeline.run(
                topic=topic, audience=audience, goal=goal, tone=tone,
                words=words, publish=True, on_stage=_on_stage,
            )
            payload = result.to_dict()
            with _runs_lock:
                _runs[result.run_id] = payload
            events.put(("done", payload))
        except Exception as exc:  # surface errors to the UI instead of hanging
            events.put(("error", {"message": str(exc)}))
        finally:
            events.put((None, None))

    threading.Thread(target=_job, daemon=True).start()

    def _gen():
        while True:
            kind, data = events.get()
            if kind is None:
                break
            yield f"event: {kind}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
