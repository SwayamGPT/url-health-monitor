import httpx
import logging
import os

log = logging.getLogger(__name__)

# Groq and Ollama both expose an OpenAI-compatible /chat/completions endpoint.
# GROQ_API_KEY set -> Groq; otherwise fall back to a local Ollama server.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
else:
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1")


class LLMError(Exception):
    pass


async def chat(system: str, user: str, max_tokens: int = 300) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        raise LLMError(str(e)) from e


INCIDENT_SYSTEM = (
    "You are an SRE assistant. Given the result of a failed HTTP health check, explain in "
    "2-3 plain-English sentences the most likely cause and what to check first. "
    "Do not invent facts that aren't implied by the data."
)

async def summarize_incident(url: str, result: dict) -> str | None:
    details = (
        f"URL: {url}\n"
        f"HTTP status: {result['status_code'] if result['status_code'] is not None else 'no response'}\n"
        f"Response time: {result['response_time_ms']:.0f} ms\n"
        f"Error: {result.get('error') or 'none'}"
    )
    try:
        return await chat(INCIDENT_SYSTEM, details, max_tokens=150)
    except LLMError as e:
        log.warning("Incident summary failed for %s: %s", url, e)
        return None


ASK_SYSTEM = (
    "You answer questions about a user's website monitoring history. Use only the context "
    "provided: per-site stats and the most relevant check records. Times are UTC. If the "
    "context doesn't contain the answer, say so. Be concise and cite dates and times."
)

async def answer_question(question: str, context: str) -> str:
    return await chat(ASK_SYSTEM, f"Context:\n{context}\n\nQuestion: {question}", max_tokens=400)
