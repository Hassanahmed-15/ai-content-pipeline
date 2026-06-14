# AI Multi-Agent Content Pipeline

A production-style, multi-agent AI automation that turns a single topic into a
fully edited, fact-checked, SEO-optimized, "published" article — built as a
self-contained Python / FastAPI service.

It demonstrates the same pattern you'd build in n8n / LangGraph (chained AI
agents with orchestration, logging, and a webhook trigger) but as testable code
that **runs end-to-end right now** — with or without an API key.

## The agent pipeline

```
 Trigger (CLI or POST /generate)
        │
        ▼
 ┌──────────────┐   research brief (JSON: summary, key points, stats, angles)
 │  1. RESEARCH │──────────────┐
 └──────────────┘              ▼
 ┌──────────────┐   full markdown draft
 │  2. WRITER   │──────────────┐
 └──────────────┘              ▼
 ┌──────────────┐   edited copy + issues + fact-check + readability
 │  3. EDITOR   │──────────────┐
 └──────────────┘              ▼
 ┌──────────────┐   title, meta description, slug, keywords, social caption
 │  4. SEO      │──────────────┐
 └──────────────┘              ▼
 ┌──────────────┐   writes <slug>.md (with front-matter) + <slug>.json sidecar
 │  5. PUBLISH  │
 └──────────────┘
```

Every stage is timed and logged, and the final run is returned as structured
JSON — the observability you'd want from a real agent workflow.

## Why it always works (the "mockable" design)

The whole thing runs **offline with no API key**, using a deterministic stub LLM
that returns correctly-shaped output for each agent. The moment you set
`OPENAI_API_KEY` (or switch `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`),
every agent makes real LLM calls — **no code changes anywhere**.
See [app/llm.py](app/llm.py).

This means you can demo it instantly, then flip it to live in one step.

## Two interfaces

### 1. Web dashboard

```bash
cd ai-content-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — type a topic, click **Generate**, and watch
each agent (research → writer → editor → seo → publish) light up live via
Server-Sent Events. You get the rendered article, an SEO/metadata panel, an
editor/fact-check report, and Copy / Download buttons. A badge at the top shows
whether you're in **LIVE** (real LLM) or **STUB** mode.

### 2. Polished CLI

```bash
python3 run.py "AI agents for small business automation" --words 700 --tone witty
```

Colored per-agent progress, timings, SEO summary, and an article preview. Files
are written to `./output/`.

### Raw API (for n8n / scripts)

```bash
curl localhost:8000/health
curl -X POST localhost:8000/generate -H 'Content-Type: application/json' \
  -d '{"topic": "AI agents for fintech document automation", "words": 700}'
# async: returns a run_id immediately, then poll
curl -X POST localhost:8000/generate/async -H 'Content-Type: application/json' \
  -d '{"topic": "RAG pipelines for SaaS support"}'
curl localhost:8000/runs/<run_id>
```

Interactive docs at `http://localhost:8000/docs`.

## Go LIVE (OpenAI by default)

```bash
cp .env.example .env
# edit .env: set OPENAI_API_KEY=sk-...   (LLM_PROVIDER=openai is the default)
```

That's it — restart the server / re-run the CLI and every agent makes real
OpenAI calls (`gpt-4o-mini` by default; set `OPENAI_MODEL=gpt-4o` for higher
quality). `/health` and the web badge flip to **LIVE**.

> Keys are read from `.env` / the environment only — never hardcoded. `.env` is
> git-ignored. To use Claude instead, set `LLM_PROVIDER=anthropic` and
> `ANTHROPIC_API_KEY`.

## Run the tests

```bash
source .venv/bin/activate
python test_api.py     # UI + health + generate + runs + 404 + validation + SSE stream
```

## Deploy

This is a long-running server (live SSE streaming + in-memory run store), so it
needs an always-on host — **not** a serverless platform. Render and Railway both
run it unchanged. Everything you tested locally keeps working in production.

> **Why not Vercel?** Vercel is serverless: short-lived, stateless functions with
> a read-only filesystem. The `/stream` SSE endpoint and the in-memory run store
> don't survive that model. Use Render/Railway for the full app.

The production entrypoint is [server.py](server.py) — it binds to the `$PORT` the
platform injects.

### Option A — Render (one-click blueprint)

1. Push this folder to a GitHub repo.
2. In Render: **New + → Blueprint**, connect the repo. Render reads
   [render.yaml](render.yaml) automatically.
3. When prompted (or under the service's **Environment**), set the secret
   `OPENAI_API_KEY` = your key. It is **not** in git.
4. Deploy. Render hits `/health` to confirm it's up, then gives you a public URL.

### Option B — Railway

1. Push to GitHub. In Railway: **New Project → Deploy from GitHub repo**.
2. Railway builds via the [Dockerfile](Dockerfile) (see [railway.json](railway.json)).
3. Add variable `OPENAI_API_KEY` in the service settings. Optionally
   `LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-4o-mini`.
4. Generate a domain under **Settings → Networking**.

### Option C — Docker (any host: Fly.io, a VPS, etc.)

```bash
docker build -t ai-content-pipeline .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... ai-content-pipeline
# open http://localhost:8000
```

**Production env vars:** `OPENAI_API_KEY` (required for live mode),
`LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-4o-mini`, `OUTPUT_DIR=/tmp/output`
(published files are ephemeral in containers — wire a DB/object store for
persistence in a real deployment).

## Project layout

```
ai-content-pipeline/
├── app/
│   ├── llm.py              # OpenAI + Claude backends + deterministic offline stub
│   ├── orchestrator.py     # chains the agents, times + logs each stage, publishes
│   ├── main.py             # FastAPI service + web UI + SSE stream
│   ├── static/
│   │   └── index.html      # the web dashboard (no build step, no deps)
│   └── agents/
│       ├── research.py     # Agent 1
│       ├── writer.py       # Agent 2
│       ├── editor.py       # Agent 3 (edit + fact-check)
│       ├── seo.py          # Agent 4
│       └── base.py         # robust JSON parsing shared by agents
├── run.py                  # polished CLI runner
├── test_api.py             # end-to-end test (UI + API + SSE)
├── requirements.txt
└── .env.example
```

## Mapping to the job requirements

| Requirement | Where it shows up |
|---|---|
| Python / FastAPI | `app/main.py`, whole codebase |
| OpenAI / Claude API | `app/llm.py` (pluggable providers; OpenAI default) |
| Agent workflows / orchestration | `app/orchestrator.py` (multi-agent chain) |
| API integrations & webhooks | FastAPI endpoints = webhook triggers; SSE streaming |
| Frontend / interface | `app/static/index.html` live dashboard |
| PostgreSQL / Redis | in-memory run store with a clear swap point in `main.py` |
| Deploy / debug production AI | structured per-stage logging, async runs, health check |

To wire this into **n8n**: use an *HTTP Request* node pointing at `POST /generate`
(or the async pair), and feed the returned JSON into Slack / CMS / DB nodes.
The service is the agent brain; n8n becomes the trigger + delivery layer.
