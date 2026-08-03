import httpx
import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import model
import asyncio

async def check_one_url(url:str)->dict:
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
        elapsed = (time.perf_counter()-start) * 1000
        return {
            "status_code": response.status_code,
            "response_time_ms": elapsed,
            "is_up": response.status_code < 400,
        }
    except httpx.RequestError():
        elapsed=(time.perf_counter()-start) * 1000
        return {
            "status_code": None,
            "response_time_ms": elapsed,
            "is_up": False,
        }


async def concurrent_check_all_sequential(urls: list[str])->list[dict]:
    tasks = [check_one_url(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results