import httpx
import time
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import model
import llm
import embeddings

log = logging.getLogger(__name__)

CHECK_TIMEOUT = 5.0
MAX_HTML_BYTES = 2_000_000


async def check_one_url(client: httpx.AsyncClient, url: str) -> dict:
    start = time.perf_counter()
    try:
        response = await client.get(url)
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "status_code": response.status_code,
            "response_time_ms": elapsed,
            "is_up": response.status_code < 400,
            "error": None if response.status_code < 400 else response.reason_phrase,
        }
    except httpx.RequestError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "status_code": None,
            "response_time_ms": elapsed,
            "is_up": False,
            "error": f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
        }


async def concurrent_check_all(urls: list[str]) -> list[dict]:
    # All requests are in flight at once: total time ~ slowest check, not the sum.
    async with httpx.AsyncClient(timeout=CHECK_TIMEOUT, follow_redirects=True) as client:
        return await asyncio.gather(*(check_one_url(client, url) for url in urls))


async def _latest_checks(db: AsyncSession, website_ids: list[int]) -> dict[int, model.Check]:
    result = await db.execute(
        select(model.Check)
        .where(model.Check.website_id.in_(website_ids))
        .order_by(model.Check.website_id, model.Check.checked_at.desc())
        .distinct(model.Check.website_id)
    )
    return {c.website_id: c for c in result.scalars().all()}


async def _incident_summary(url: str, result: dict, previous: model.Check | None) -> str | None:
    # Only failed checks hit the LLM. During an ongoing outage with the same symptoms,
    # reuse the previous explanation instead of re-asking every 30 seconds.
    if result["is_up"]:
        return None
    if (
        previous is not None
        and not previous.is_up
        and previous.status_code == result["status_code"]
        and previous.ai_summary
    ):
        return previous.ai_summary
    return await llm.summarize_incident(url, result)


async def check_and_store(db: AsyncSession, websites: list[model.Website]) -> list[model.Check]:
    """Check the given websites concurrently, summarize failures, embed and store the results."""
    if not websites:
        return []
    results = await concurrent_check_all([w.url for w in websites])
    previous = await _latest_checks(db, [w.id for w in websites])
    summaries = await asyncio.gather(
        *(_incident_summary(w.url, r, previous.get(w.id)) for w, r in zip(websites, results))
    )

    now = datetime.utcnow()
    checks = [
        model.Check(
            website_id=w.id,
            status_code=r["status_code"],
            response_time_ms=r["response_time_ms"],
            is_up=r["is_up"],
            error=r["error"],
            checked_at=now,
            ai_summary=summary,
        )
        for w, r, summary in zip(websites, results, summaries)
    ]

    try:
        vectors = await embeddings.embed([embeddings.describe_check(w.url, c) for w, c in zip(websites, checks)])
    except Exception as e:
        log.warning("Embedding failed: %s", e)
        vectors = None
    if vectors:
        for check, vector in zip(checks, vectors):
            check.embedding = vector

    db.add_all(checks)
    await db.commit()
    return checks


async def fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str | None, str | None]:
    """Returns (html, error)."""
    try:
        response = await client.get(url)
        if response.status_code >= 400:
            return None, f"HTTP {response.status_code} {response.reason_phrase}"
        return response.text[:MAX_HTML_BYTES], None
    except httpx.RequestError as e:
        return None, f"{type(e).__name__}: {e}"
