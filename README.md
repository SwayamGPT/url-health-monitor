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
| Auth | Short-lived JWT + rotating refresh token, both in httpOnly cookies | Protects tokens from XSS (JS can't read them); `SameSite=Lax` mitigates CSRF; a leaked access token expires in 15 min |
| Migrations | Alembic (async) | Versioned, reviewable schema changes instead of `create_all` |
| Rate limiting | Redis (sliding window, Lua) | `/ask` limits hold across workers and replicas |
| Frontend | React (Vite) | Component-based UI, fast dev server |
| Concurrency (I/O) | `asyncio` + `httpx.AsyncClient` | Check many URLs concurrently — total time ≈ slowest single check, not the sum |
| Concurrency (CPU) | `multiprocessing` via `run_in_executor` | Bulk HTML analysis is CPU-bound; sidesteps the GIL for real parallelism |
| LLM | OpenRouter (Llama 3.1 8B by default) or local Ollama | One OpenAI-compatible API in front of many models, low cost, model is a config change |
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
        OpenRouter / Ollama LLM
         (incident summaries + RAG answers)
```

### Data model
- `users` — id, email, hashed_password
- `refresh_tokens` — id, user_id (FK → users), token_hash (sha256), created_at, expires_at, revoked_at
- `websites` — id, url, owner_id (FK → users), created_at — unique per (owner_id, url)
- `checks` — id, website_id (FK → websites, cascade delete), status_code, response_time_ms, is_up, error, checked_at, ai_summary, embedding (vector(384))

## Key design decisions

**Why async SQLAlchemy over sync?** Routes await DB calls instead of blocking the event loop, so one slow query doesn't stall other requests being served concurrently.

**Why check URLs with `asyncio.gather` instead of a loop?** Checking is I/O-bound (waiting on network). Sequential checks wait one at a time; concurrent checks are all "in flight" simultaneously, so total time approximates the slowest single request rather than the sum of all of them.

**Why multiprocessing (not asyncio) for HTML analysis?** Text analysis is CPU-bound — actual computation, not waiting. Asyncio doesn't help with CPU-bound work due to the GIL; multiprocessing uses separate processes to get real parallelism. Fetching (I/O) and analyzing (CPU) are deliberately split between asyncio and multiprocessing, bridged via `run_in_executor` so the CPU-heavy work doesn't block the event loop.

**Why JWT in an httpOnly cookie instead of localStorage?** localStorage is readable by JavaScript, so an XSS vulnerability could steal the token. An httpOnly cookie can't be read by JS at all. Trade-off: cookies are vulnerable to CSRF, mitigated with `SameSite=Lax`.

**Why short-lived access tokens plus refresh tokens?** A JWT can't be revoked before it expires, so a long-lived one is a long-lived risk if it leaks. Access tokens now last 15 minutes; a 7-day opaque refresh token (stored only as a SHA-256 hash) gets a new pair from `/refresh`. Refresh tokens rotate on every use, and presenting an already-rotated token revokes all of that user's sessions, since that only happens if a token was copied. Logout revokes the refresh token server-side. The frontend's axios interceptor refreshes transparently on a 401 and shares one in-flight refresh across concurrent requests.

**Why Redis for rate limiting?** An in-process counter is per worker: with 4 uvicorn workers a "10 per minute" limit is really 40. The limiter keeps a per-user sorted set of timestamps in Redis and checks-and-adds in one Lua script, so concurrent requests can't both slip under the limit. If `REDIS_URL` isn't set it falls back to the in-process window (fine for local dev); if Redis is down it logs and allows the request rather than taking `/ask` offline.

**Why pgvector instead of a dedicated vector DB (Pinecone/FAISS)?** The vector data (check embeddings) lives naturally alongside the relational data it describes — one database, one connection pool, no extra service to run. A dedicated vector DB would make more sense for a large, standalone document corpus unrelated to relational records.

**Why a local embedding model instead of an API for embeddings?** Every check record gets embedded — potentially thousands of rows. A local model (`all-MiniLM-L6-v2`) avoids per-call API cost and latency for something that doesn't need top-tier embedding quality.

**Why OpenRouter (or Ollama) instead of a single vendor's API?** OpenRouter puts hundreds of models (open and proprietary, including free `:free` variants) behind one OpenAI-compatible endpoint, so switching models is just `LLM_MODEL` and no code changes. The default, a small open Llama model, is cheap and plenty for two-sentence incident summaries. Ollama runs fully locally with no API key, at the cost of depending on local hardware.

**Why only call the LLM on failed checks, not every check?** LLM calls cost time and (for hosted models) money. Gating the incident-summary call behind `if not is_up` avoids calling it on every healthy 30-second check. During an ongoing outage with the same status, the previous explanation is reused instead of asking again every cycle.

## Setup

### Docker (everything)
```bash
cp .env.example .env   # then set SECRET_KEY and OPENROUTER_API_KEY
docker compose up --build
```
Frontend: http://localhost:3000 · API: http://localhost:8080 (docs at `/docs`).

### Backend
```bash
cd backend
pip install -r requirements.txt
docker run --name url-monitor-db -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=urlmonitor -p 5432:5432 -d pgvector/pgvector:pg16
alembic upgrade head          # create/upgrade the schema (also enables the vector extension)
uvicorn main:app --reload
```
Optionally run Redis (`docker run -p 6379:6379 -d redis:7-alpine`) and set `REDIS_URL` for shared rate limiting.

After changing `model.py`, generate a migration with `alembic revision --autogenerate -m "describe change"`, review it, and commit it. Docker runs `alembic upgrade head` automatically before starting the API. The embedding model (~90 MB) is downloaded on first use; if it can't be loaded, monitoring keeps working and only `/ask` returns 503.

> Databases created before migrations were added (by the old `create_all` startup) don't match the initial migration. Reset them with `docker compose down -v` (or drop the database) and let `alembic upgrade head` build the schema.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment variables
See `.env.example`. The main ones:
```
DATABASE_URL=postgresql+asyncpg://postgres:pass@localhost:5432/urlmonitor
SECRET_KEY=your-jwt-secret
OPENROUTER_API_KEY=your-openrouter-key   # or run Ollama locally instead
```
Optional: `LLM_BASE_URL` / `LLM_MODEL` (defaults: OpenRouter `meta-llama/llama-3.1-8b-instruct`, or Ollama `llama3.1` at `http://localhost:11434/v1` when no OpenRouter key is set — from inside Docker use `http://host.docker.internal:11434/v1`), `COOKIE_SECURE=true` behind HTTPS, `CORS_ORIGINS`, `CHECK_INTERVAL_SECONDS` (default 30), `ASK_RATE_LIMIT` (questions per user per minute, default 10), `REDIS_URL`, `ACCESS_TOKEN_MINUTES` (default 15), `REFRESH_TOKEN_DAYS` (default 7).

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create a user account |
| POST | `/token` | Log in, sets access + refresh cookies |
| POST | `/refresh` | Rotate the refresh token and issue a new access token |
| POST | `/logout` | Revokes the refresh token and clears both cookies |
| GET | `/me` | Current user (used by the frontend to restore a session) |
| POST | `/websites` | Add a URL to monitor |
| GET | `/websites` | List monitored URLs with latest status and AI summary (joined) |
| DELETE | `/websites` | Remove a monitored URL (`{"url": ...}` body) and its history |
| GET | `/websites/{id}/history` | Past check results for one URL |
| POST | `/websites/check-all` | Manually trigger a concurrent check of all URLs |
| POST | `/websites/analyze` | Bulk HTML analysis (multiprocessing) |
| POST | `/ask` | Natural-language Q&A over monitoring history (RAG), rate limited per user |

Background task: a scheduled loop re-checks all URLs every 30 seconds automatically via FastAPI's `lifespan` startup hook and `asyncio.create_task`.

How `/ask` works: the question is embedded with the same local model, the 20 nearest check records (pgvector cosine distance, filtered to the caller's sites) are retrieved, and they're sent to the LLM together with per-site uptime stats so aggregate questions ("what's my uptime?") don't depend on retrieval alone.
