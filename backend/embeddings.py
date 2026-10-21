import asyncio
import logging
import os
import threading
import time

log = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # output size of all-MiniLM-L6-v2

RETRY_AFTER_SECONDS = 300

_model = None
_failed_at = None
_lock = threading.Lock()

def _load_model():
    global _model, _failed_at
    with _lock:
        if _model is None and (_failed_at is None or time.monotonic() - _failed_at > RETRY_AFTER_SECONDS):
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(EMBEDDING_MODEL)
            except Exception as e:
                # Monitoring keeps working without embeddings; only /ask degrades.
                _failed_at = time.monotonic()
                log.warning("Embedding model unavailable, skipping embeddings: %s", e)
    return _model

def _encode(texts: list[str]) -> list[list[float]] | None:
    model = _load_model()
    if model is None:
        return None
    return model.encode(texts, normalize_embeddings=True).tolist()

async def embed(texts: list[str]) -> list[list[float]] | None:
    """Embed texts off the event loop. Returns None if the model can't be loaded."""
    if not texts:
        return []
    return await asyncio.to_thread(_encode, texts)

def describe_check(url: str, check) -> str:
    """Plain-text rendering of a check; this is what gets embedded and later shown to the LLM."""
    when = check.checked_at.strftime("%Y-%m-%d %H:%M UTC")
    state = "UP" if check.is_up else "DOWN"
    text = f"{url} was {state} at {when}"
    text += f", HTTP status {check.status_code}" if check.status_code is not None else ", no HTTP response"
    if check.response_time_ms is not None:
        text += f", response time {check.response_time_ms:.0f} ms"
    if check.error:
        text += f", error: {check.error}"
    text += "."
    if check.ai_summary:
        text += f" Likely cause: {check.ai_summary}"
    return text
