"""LLM settings router — view / update / test LLM provider config at runtime.

Updates are applied to the in-memory settings immediately (so running reviews
pick them up) and persisted to backend/.env so they survive restarts.
API keys are never returned in clear text.
"""
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ..config import settings, BACKEND_DIR
from ..services.llm_client import llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings/llm", tags=["settings"])

ENV_FILE = BACKEND_DIR / ".env"

# Fields that may be updated through the API, mapped to .env variable names
_PERSIST_FIELDS = {
    "base_url": "LLM_BASE_URL",
    "model": "LLM_MODEL",
    "temperature": "LLM_TEMPERATURE",
    "max_tokens": "LLM_MAX_TOKENS",
    "api_key": "LLM_API_KEY",
}


def _mask_key(key: str) -> str:
    """Mask an API key, showing only head/tail characters."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:5]}{'*' * 6}{key[-4:]}"


def _current_view() -> dict:
    return {
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "concurrency": settings.llm_concurrency,
        "api_key_set": bool(settings.llm_api_key),
        "api_key_masked": _mask_key(settings.llm_api_key),
    }


class LLMSettingsUpdate(BaseModel):
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=64, le=131072)
    # Empty/None means "keep the current key" (key is never echoed back)
    api_key: str | None = None


class LLMTestRequest(BaseModel):
    # Optional overrides so the UI can test before saving
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


@router.get("")
async def get_llm_settings():
    """Return current LLM configuration (API key masked)."""
    return _current_view()


@router.put("")
async def update_llm_settings(req: LLMSettingsUpdate):
    """Update LLM configuration at runtime and persist it to .env."""
    updates: dict[str, object] = {}
    if req.base_url is not None and req.base_url.strip():
        updates["base_url"] = req.base_url.strip()
    if req.model is not None and req.model.strip():
        updates["model"] = req.model.strip()
    if req.temperature is not None:
        updates["temperature"] = req.temperature
    if req.max_tokens is not None:
        updates["max_tokens"] = req.max_tokens
    if req.api_key is not None and req.api_key.strip():
        updates["api_key"] = req.api_key.strip()

    if not updates:
        raise HTTPException(400, "No fields to update")

    # 1. Apply to in-memory settings
    for field, value in updates.items():
        setattr(settings, f"llm_{field}", value)

    # 2. Rebuild the LLM client so new calls use the new config
    llm_client.reconfigure()

    # 3. Persist to .env (create if missing)
    try:
        from dotenv import set_key

        for field, value in updates.items():
            set_key(str(ENV_FILE), _PERSIST_FIELDS[field], str(value), quote_mode="never")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to persist settings to .env: %s", e)

    logger.info("LLM settings updated: %s", {k: v for k, v in updates.items() if k != "api_key"})
    return _current_view()


@router.post("/test")
async def test_llm_connection(req: LLMTestRequest):
    """Send a minimal chat completion to verify connectivity / credentials."""
    base_url = (req.base_url or settings.llm_base_url).strip()
    model = (req.model or settings.llm_model).strip()
    api_key = (req.api_key or "").strip() or settings.llm_api_key

    if not api_key:
        raise HTTPException(400, "No API key configured")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    start = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            max_tokens=16,
            temperature=0,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Connection failed: {e}")

    latency_ms = int((time.perf_counter() - start) * 1000)
    return {
        "ok": True,
        "model": model,
        "latency_ms": latency_ms,
        "reply": (resp.choices[0].message.content or "").strip()[:64],
    }
