"""LLM client — DeepSeek API (OpenAI-compatible) with concurrency limiting."""
import asyncio
import json
import logging
import re
from typing import Any
from openai import AsyncOpenAI
from ..config import settings

logger = logging.getLogger(__name__)


def salvage_truncated_json(text: str) -> str | None:
    """Attempt to salvage a truncated JSON string.

    Scans char-by-char tracking string state and bracket nesting, finds the
    last position after a completely-closed nested value, cuts there and
    appends the missing closing brackets. Returns None if not salvageable.
    """
    s = text.strip()
    # Strip markdown fences if present
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)

    stack: list[str] = []
    in_str = False
    esc = False
    cut = -1          # last safe cut position (exclusive)
    cut_stack: list[str] = []

    for i, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
            if not stack:
                # Top-level value fully closed — use this prefix
                return s[:i + 1]
            cut = i + 1
            cut_stack = list(stack)

    # Even if we ended inside a string (typical truncation), the last recorded
    # cut point (right after a fully-closed nested value) is still usable.
    if cut <= 0 or not cut_stack:
        return None

    truncated = s[:cut].rstrip()
    # Remove trailing comma if the cut happened right before an omitted element
    while truncated.endswith(","):
        truncated = truncated[:-1].rstrip()
    closers = "".join("}" if c == "{" else "]" for c in reversed(cut_stack))
    candidate = truncated + closers
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return None


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=120.0,
        )
        self._semaphore = asyncio.Semaphore(settings.llm_concurrency)
        self._call_counter = 0

    def reconfigure(self):
        """Rebuild the underlying client after settings change at runtime."""
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=120.0,
        )
        self._semaphore = asyncio.Semaphore(settings.llm_concurrency)

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        retry: int = 1,
    ) -> str:
        """Call LLM and return raw text response. Retries on JSON parse failure."""
        temp = temperature if temperature is not None else settings.llm_temperature
        tokens = max_tokens or settings.llm_max_tokens

        async with self._semaphore:
            self._call_counter += 1
            kwargs: dict[str, Any] = {
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temp,
                "max_tokens": tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            for attempt in range(retry + 1):
                try:
                    resp = await self.client.chat.completions.create(**kwargs)
                    content = resp.choices[0].message.content or ""

                    if json_mode:
                        # Validate it's parseable JSON
                        try:
                            json.loads(content)
                        except json.JSONDecodeError as e:
                            # Truncated output? Try to salvage partial JSON
                            salvaged = salvage_truncated_json(content)
                            if salvaged is not None:
                                logger.warning(
                                    f"JSON truncated (finish_reason="
                                    f"{resp.choices[0].finish_reason}), "
                                    f"salvaged partial result"
                                )
                                content = salvaged
                            elif attempt < retry:
                                logger.warning(
                                    f"JSON parse failed (attempt {attempt+1}), "
                                    f"retrying. Error: {e}"
                                )
                                # Feed error back to LLM
                                kwargs["messages"].append({
                                    "role": "assistant",
                                    "content": content
                                })
                                kwargs["messages"].append({
                                    "role": "user",
                                    "content": (
                                        f"Your previous response was truncated or "
                                        f"not valid JSON: {e}\n"
                                        "Please output ONLY valid JSON. Be concise: "
                                        "each description under 100 characters, "
                                        "at most 15 issues, no markdown fences."
                                    )
                                })
                                continue
                            else:
                                raise
                    return content

                except Exception as e:
                    if attempt < retry:
                        logger.warning(f"LLM call failed (attempt {attempt+1}): {e}")
                        await asyncio.sleep(1)
                        continue
                    raise

            return ""

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> dict:
        """Call LLM and return parsed JSON dict."""
        raw = await self.complete(system_prompt, user_prompt, json_mode=True, **kwargs)
        return json.loads(raw)


llm_client = LLMClient()
