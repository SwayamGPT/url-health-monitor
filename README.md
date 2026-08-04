# URL Health Monitor

A full-stack concurrent website monitoring tool with AI-powered incident analysis and natural-language search over monitoring history. Built to demonstrate async concurrency, relational + vector data modeling, and pragmatic LLM integration.

## What it does

- Add URLs to monitor; the system checks them concurrently on a schedule and tracks uptime, status codes, and response times over time.
- Dashboard shows live status (up/down), response time, and last-checked time per site.
- When a site goes down, an LLM generates a plain-English explanation of the likely cause.
- Ask natural-language questions about monitoring history ("when did X go down last week and why?") via retrieval-augmented generation over past incidents.
- Auth-scoped: each user only sees and manages their own monitored sites.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI (async) | Native async support, automatic validation via Pydantic, auto-generated docs |
| DB | PostgreSQL + SQLAlchemy (async) + asyncpg | Async driver keeps DB calls non-blocking inside async routes |
| Auth | JWT in httpOnly cookie | Protects token from XSS (JS can't read it); `SameSite=Lax` mitigates CSRF |
| Frontend | React (Vite) | Component-based UI, fast dev server |
| Concurrency (I/O) | `asyncio` + `httpx.AsyncClient` | Check many URLs concurrently — total time ≈ slowest single check, not the sum |
| Concurrency (CPU) | `multiprocessing` via `run_in_executor` | Bulk HTML analysis is CPU-bound; sidesteps the GIL for real parallelism |
| LLM | Groq (Llama 3.1, free tier) or local Ollama | Free/low-cost, OpenAI-compatible API, fast inference |
| Embeddings | `sentence-transformers` (local, `all-MiniLM-L6-v2`) | Free, fast, no per-call API cost for embedding thousands of check records |
| Vector search | pgvector (Postgres extension) | Reuses existing Postgres instance — no separate vector DB service to run |

## Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   React      │ ──── │   FastAPI         │ ──── │   PostgreSQL     │
│   (Vite)     │      │   (async routes)  │      │   + pgvector     │
└─────────────┘      └──────────────────┘      └─────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
            asyncio.gather        multiprocessing
            (URL health checks)   (HTML content analysis)
                    │
              Groq / Ollama LLM
         (incident summaries + RAG answers)
```

### Data model
- `users` — id, email, hashed_password
- `websites` — id, url, owner_id (FK → users), created_at
- `checks` — id, website_id (FK → websites), status_code, response_time_ms, is_up, checked_at, ai_summary, embedding (vector)

## Key design decisions

**Why async SQLAlchemy over sync?** Routes await DB calls instead of blocking the event loop, so one slow query doesn't stall other requests being served concurrently.

**Why check URLs with `asyncio.gather` instead of a loop?** Checking is I/O-bound (waiting on network). Sequential checks wait one at a time; concurrent checks are all "in flight" simultaneously, so total time approximates the slowest single request rather than the sum of all of them.

**Why multiprocessing (not asyncio) for HTML analysis?** Text analysis is CPU-bound — actual computation, not waiting. Asyncio doesn't help with CPU-bound work due to the GIL; multiprocessing uses separate processes to get real parallelism. Fetching (I/O) and analyzing (CPU) are deliberately split between asyncio and multiprocessing, bridged via `run_in_executor` so the CPU-heavy work doesn't block the event loop.

**Why JWT in an httpOnly cookie instead of localStorage?** localStorage is readable by JavaScript, so an XSS vulnerability could steal the token. An httpOnly cookie can't be read by JS at all. Trade-off: cookies are vulnerable to CSRF, mitigated with `SameSite=Lax`.

**Why pgvector instead of a dedicated vector DB (Pinecone/FAISS)?** The vector data (check embeddings) lives naturally alongside the relational data it describes — one database, one connection pool, no extra service to run. A dedicated vector DB would make more sense for a large, standalone document corpus unrelated to relational records.

**Why a local embedding model instead of an API for embeddings?** Every check record gets embedded — potentially thousands of rows. A local model (`all-MiniLM-L6-v2`) avoids per-call API cost and latency for something that doesn't need top-tier embedding quality.

**Why a free/local LLM (Groq or Ollama) instead of a paid API?** Keeps the project runnable without billing setup. Groq offers fast inference on open models (Llama) with a usable free tier; Ollama runs fully locally with no API key, at the cost of depending on local hardware.

**Why only call the LLM on failed checks, not every check?** LLM calls cost time and (for hosted models) money. Gating the incident-summary call behind `if not is_up` avoids calling it on every healthy 30-second check.

## Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
docker run --name url-monitor-db -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=urlmonitor -p 5432:5432 -d postgres
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment variables
```
DATABASE_URL=postgresql+asyncpg://postgres:pass@localhost:5432/urlmonitor
SECRET_KEY=your-jwt-secret
GROQ_API_KEY=your-groq-key   # or run Ollama locally instead
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create a user account |
| POST | `/token` | Log in, sets auth cookie |
| POST | `/logout` | Clears auth cookie |
| POST | `/websites` | Add a URL to monitor |
| GET | `/websites` | List monitored URLs with latest status (joined) |
| DELETE | `/websites` | Remove a monitored URL |
| GET | `/websites/{id}/history` | Past check results for one URL |
| POST | `/websites/check-all` | Manually trigger a concurrent check of all URLs |
| POST | `/websites/analyze` | Bulk HTML analysis (multiprocessing) |
| POST | `/ask` | Natural-language Q&A over monitoring history (RAG) |

Background task: a scheduled loop re-checks all URLs every 30 seconds automatically via FastAPI's `lifespan` startup hook and `asyncio.create_task`.
ived access tokens
- Rate limiting on `/ask` to control LLM call volume
