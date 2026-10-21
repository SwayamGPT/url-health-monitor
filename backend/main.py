from fastapi import FastAPI, Depends, HTTPException, Response
from sqlalchemy import delete, func, select, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, get_db
import model, schemas, checker, analyzer, embeddings, llm
from ratelimit import RateLimiter
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import asyncio
import httpx
import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
import auth
from auth import get_current_user, pwd_context

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("url-monitor")

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "30"))
ASK_RATE_LIMIT = int(os.getenv("ASK_RATE_LIMIT", "10"))  # questions per user per minute
ASK_TOP_K = 20

ask_limiter = RateLimiter(os.getenv("REDIS_URL"), limit=ASK_RATE_LIMIT, window_seconds=60, prefix="ratelimit:ask")

background_task = None
process_pool: ProcessPoolExecutor | None = None


async def periodic_checker():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(model.Website))
                websites = result.scalars().all()
                if websites:
                    await checker.check_and_store(db, websites)
                    log.info("Checked %d websites", len(websites))
        except Exception:
            log.exception("Background check failed")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task, process_pool
    # Schema is managed by Alembic: run `alembic upgrade head` before starting the app.
    log.info("/ask rate limiter backend: %s", ask_limiter.backend)
    process_pool = ProcessPoolExecutor()
    background_task = asyncio.create_task(periodic_checker())
    yield
    background_task.cancel()
    try:
        await background_task
    except asyncio.CancelledError:
        pass
    process_pool.shutdown(cancel_futures=True)
    await ask_limiter.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_credentials=True,  # required for the auth cookie on cross-origin requests
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- auth ----------

@app.post("/register", response_model=schemas.UserOut, status_code=201)
async def register(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    user = model.User(email=user_in.email.lower(), hashed_password=pwd_context.hash(user_in.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(400, "Email already registered")
    await db.refresh(user)
    return user

@app.post("/token")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(model.User).where(model.User.email == form_data.username.lower()))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    # Tokens only travel in httpOnly cookies, never in the response body.
    await auth.issue_tokens(db, response, user.id)
    await db.commit()
    return {"message": "logged in"}

@app.post("/refresh")
async def refresh(response: Response, refresh_token: str | None = Depends(auth.refresh_cookie_scheme), db: AsyncSession = Depends(get_db)):
    await auth.rotate_refresh_token(db, response, refresh_token)
    return {"message": "refreshed"}

@app.post("/logout")
async def logout(response: Response, refresh_token: str | None = Depends(auth.refresh_cookie_scheme), db: AsyncSession = Depends(get_db)):
    await auth.revoke_refresh_token(db, refresh_token)
    await db.commit()
    auth.clear_auth_cookies(response)
    return {"message": "logged out"}

@app.get("/me", response_model=schemas.UserOut)
async def me(user: model.User = Depends(get_current_user)):
    return user


# ---------- websites ----------

async def get_owned_website(website_id: int, db: AsyncSession, user: model.User) -> model.Website:
    result = await db.execute(
        select(model.Website).where(model.Website.id == website_id, model.Website.owner_id == user.id)
    )
    website = result.scalar_one_or_none()
    if not website:
        raise HTTPException(404, "Website not found")
    return website

async def get_user_websites(db: AsyncSession, user: model.User) -> list[model.Website]:
    result = await db.execute(select(model.Website).where(model.Website.owner_id == user.id))
    return result.scalars().all()

@app.post("/websites", response_model=schemas.WebsiteOut, status_code=201)
async def add_website(website: schemas.WebsiteCreate, db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    db_website = model.Website(url=str(website.url), owner_id=user.id)
    db.add(db_website)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(400, "URL already being monitored")
    await db.refresh(db_website)
    return db_website

@app.get("/websites", response_model=list[schemas.WebsiteOut])
async def list_websites(db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    latest_check_subq = (
        select(
            model.Check.website_id,
            func.max(model.Check.checked_at).label("max_checked_at")
        )
        .group_by(model.Check.website_id)
        .subquery()
    )

    stmt = (
        select(
            model.Website,
            model.Check.is_up,
            model.Check.status_code,
            model.Check.response_time_ms,
            model.Check.checked_at,
            model.Check.ai_summary,
        )
        .outerjoin(latest_check_subq, model.Website.id == latest_check_subq.c.website_id)
        .outerjoin(
            model.Check,
            (model.Check.website_id == latest_check_subq.c.website_id)
            & (model.Check.checked_at == latest_check_subq.c.max_checked_at)
        )
        .where(model.Website.owner_id == user.id)
        .order_by(model.Website.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": w.id,
            "url": w.url,
            "created_at": w.created_at,
            "is_up": is_up,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "last_checked": checked_at,
            "ai_summary": ai_summary,
        }
        for w, is_up, status_code, response_time_ms, checked_at, ai_summary in rows
    ]

@app.delete("/websites")
async def delete_website(website: schemas.WebsiteDelete, db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    stmt = delete(model.Website).where(
        model.Website.url == str(website.url), model.Website.owner_id == user.id
    )
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="URL not found.")

    await db.commit()
    return {"deleted": str(website.url)}

@app.post("/websites/check-all")
async def check_all_websites(db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    websites = await get_user_websites(db, user)
    start = time.perf_counter()
    checks = await checker.check_and_store(db, websites)
    return {
        "checked": len(checks),
        "up": sum(c.is_up for c in checks),
        "elapsed_ms": round((time.perf_counter() - start) * 1000),
    }

@app.post("/websites/analyze", response_model=list[schemas.AnalysisOut])
async def analyze_websites(db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    websites = await get_user_websites(db, user)

    # I/O-bound: fetch every page concurrently.
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        fetched = await asyncio.gather(*(checker.fetch_html(client, w.url) for w in websites))

    # CPU-bound: parse in worker processes so the event loop (and the GIL) aren't blocked.
    loop = asyncio.get_running_loop()
    jobs = [
        loop.run_in_executor(process_pool, analyzer.analyze_html, html) if html is not None else None
        for html, _ in fetched
    ]
    analyses = await asyncio.gather(*(j for j in jobs if j is not None), return_exceptions=True)
    analyses_iter = iter(analyses)

    out = []
    for w, (html, error), job in zip(websites, fetched, jobs):
        item = {"website_id": w.id, "url": w.url, "error": error}
        if job is not None:
            analysis = next(analyses_iter)
            if isinstance(analysis, Exception):
                item["error"] = f"Analysis failed: {analysis}"
            else:
                item.update(analysis)
        out.append(item)
    return out

@app.get("/websites/{website_id}/history", response_model=list[schemas.CheckOut])
async def get_history(website_id: int, limit: int = 50, db: AsyncSession = Depends(get_db), user: model.User = Depends(get_current_user)):
    await get_owned_website(website_id, db, user)
    result = await db.execute(
        select(model.Check)
        .where(model.Check.website_id == website_id)
        .order_by(model.Check.checked_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    return result.scalars().all()


# ---------- RAG over monitoring history ----------

async def enforce_ask_rate_limit(user: model.User = Depends(get_current_user)) -> model.User:
    retry_after = await ask_limiter.hit(str(user.id))
    if retry_after:
        raise HTTPException(
            429,
            f"Rate limit: {ASK_RATE_LIMIT} questions per minute. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    return user

async def site_stats_context(db: AsyncSession, user: model.User) -> str:
    stmt = (
        select(
            model.Website.url,
            func.count(model.Check.id),
            func.sum(case((model.Check.is_up, 1), else_=0)),
            func.avg(model.Check.response_time_ms),
            func.min(model.Check.checked_at),
            func.max(case((model.Check.is_up == False, model.Check.checked_at))),  # noqa: E712
        )
        .outerjoin(model.Check, model.Check.website_id == model.Website.id)
        .where(model.Website.owner_id == user.id)
        .group_by(model.Website.id)
    )
    lines = []
    for url, total, up, avg_ms, first, last_down in (await db.execute(stmt)).all():
        if not total:
            lines.append(f"- {url}: no checks yet")
            continue
        lines.append(
            f"- {url}: {total} checks since {first:%Y-%m-%d %H:%M}, uptime {100 * (up or 0) / total:.1f}%, "
            f"avg response {avg_ms or 0:.0f} ms, last down: {f'{last_down:%Y-%m-%d %H:%M}' if last_down else 'never'}"
        )
    return "\n".join(lines) or "(no monitored sites)"

@app.post("/ask", response_model=schemas.AskResponse)
async def ask(req: schemas.AskRequest, db: AsyncSession = Depends(get_db), user: model.User = Depends(enforce_ask_rate_limit)):
    vectors = await embeddings.embed([req.question])
    if not vectors:
        raise HTTPException(503, "Embedding model unavailable")

    # Nearest check records by cosine distance, restricted to this user's sites.
    result = await db.execute(
        select(model.Check, model.Website.url)
        .join(model.Website, model.Check.website_id == model.Website.id)
        .where(model.Website.owner_id == user.id, model.Check.embedding.is_not(None))
        .order_by(model.Check.embedding.cosine_distance(vectors[0]))
        .limit(ASK_TOP_K)
    )
    rows = result.all()
    rows.sort(key=lambda r: r[0].checked_at)

    context = (
        f"Current time: {datetime.utcnow():%Y-%m-%d %H:%M} UTC\n\n"
        f"Per-site stats:\n{await site_stats_context(db, user)}\n\n"
        "Most relevant check records:\n"
        + ("\n".join(f"- {embeddings.describe_check(url, c)}" for c, url in rows) or "(none)")
    )
    try:
        answer = await llm.answer_question(req.question, context)
    except llm.LLMError as e:
        log.warning("LLM call failed for /ask: %s", e)
        raise HTTPException(503, "LLM unavailable")

    return {
        "answer": answer,
        "sources": [
            {"check_id": c.id, "url": url, "checked_at": c.checked_at, "is_up": c.is_up, "status_code": c.status_code}
            for c, url in rows
        ],
    }


@app.get("/health")
async def health():
    return {"ok": True}
