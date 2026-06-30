"""Base Agent class with tool-use support and function-calling fallback."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Any, Callable
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.agents.tools import Tool, tool_registry

logger = logging.getLogger(__name__)

MODEL_PROVIDER_MAP = {
    "deepseek-v3": {
        "api_key_attr": "LLM_DEEPSEEK_API_KEY",
        "base_url_attr": "LLM_DEEPSEEK_BASE_URL",
        "model_id": "deepseek-chat",
    },
    "glm-4": {
        "api_key_attr": "LLM_ZHIPU_API_KEY",
        "base_url_attr": "LLM_ZHIPU_BASE_URL",
        "model_id": "glm-4-plus",
    },
    "glm-4v-plus": {
        "api_key_attr": "LLM_ZHIPU_API_KEY",
        "base_url_attr": "LLM_ZHIPU_BASE_URL",
        "model_id": "glm-4v-plus",
    },
    "glm-4v-flash": {
        "api_key_attr": "LLM_ZHIPU_API_KEY",
        "base_url_attr": "LLM_ZHIPU_BASE_URL",
        "model_id": "glm-4v-flash",
    },
    "qwen-vl-max": {
        "api_key_attr": "LLM_SILICONFLOW_API_KEY",
        "base_url_attr": "LLM_SILICONFLOW_BASE_URL",
        "model_id": "deepseek-ai/DeepSeek-V3",
    },
    "gemini-2.0-flash": {
        "api_key_attr": "LLM_GEMINI_API_KEY",
        "base_url_attr": "LLM_GEMINI_BASE_URL",
        "model_id": "gemini-2.0-flash",
    },
    "gpt-4o": {
        "api_key_attr": "LLM_SILICONFLOW_API_KEY",
        "base_url_attr": "LLM_SILICONFLOW_BASE_URL",
        "model_id": "deepseek-ai/DeepSeek-V3",
    },
}

FUNCTION_CALLING_CAPABLE = {
    "deepseek-v3": True,
    "glm-4": True,
    "qwen-vl-max": True,
    "gpt-4o": True,
    "gemini-2.0-flash": True,
    "glm-4v-plus": False,
    "glm-4v-flash": False,
}


def _get_provider_for_model(model: str) -> dict:
    if model not in MODEL_PROVIDER_MAP:
        logger.warning(f"Unknown model '{model}', falling back to deepseek-v3")
        model = "deepseek-v3"
    entry = MODEL_PROVIDER_MAP[model]
    api_key = getattr(settings, entry["api_key_attr"], "")
    base_url = getattr(settings, entry["base_url_attr"], settings.LLM_BASE_URL)
    return {"api_key": api_key, "base_url": base_url, "model_id": entry["model_id"]}


@dataclass
class AgentMemory:
    """Per-agent memory across review sessions."""
    name: str
    history: list[dict] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)

    def record(self, entry: dict):
        self.history.append(entry)
        if len(self.history) > 100:
            self.history = self.history[-100:]

    def context_summary(self) -> str:
        if not self.history:
            return ""
        recent = self.history[-5:]
        lines = ["## 近期审查历史"]
        for h in recent:
            lines.append(f"- [{h.get('severity','?')}] {h.get('title','')}")
        return "\n".join(lines)


class BaseAgent:
    """Foundation agent class: encapsulates identity, tools, memory, and LLM interaction."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        model: str = "deepseek-v3",
        tools: list[Tool] | None = None,
        max_tool_rounds: int = 5,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        enable_function_calling: bool = True,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.tools: list[Tool] = tools or []
        self.max_tool_rounds = max_tool_rounds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enable_function_calling = enable_function_calling
        self._memory = AgentMemory(name=name)
        self._provider = _get_provider_for_model(model)

    def register_tool(self, tool: Tool):
        self.tools.append(tool)

    @property
    def supports_function_calling(self) -> bool:
        if not self.enable_function_calling:
            return False
        return FUNCTION_CALLING_CAPABLE.get(self.model, False)

    @property
    def tool_registry(self):
        return tool_registry

    def _build_llm(self, bind_tools: bool = False) -> ChatOpenAI:
        llm = ChatOpenAI(
            model=self._provider["model_id"],
            openai_api_key=self._provider["api_key"],
            base_url=self._provider["base_url"],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        if bind_tools and self.supports_function_calling and self.tools:
            tool_schemas = [t.to_openai_schema() for t in self.tools]
            llm = llm.bind_tools(tool_schemas)
        return llm

    def _build_messages(self, user_content: str) -> list[dict]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def run_json_mode(self, user_content: str, timeout: float = 120.0) -> str:
        """Run in JSON instruction mode (fallback when function calling unavailable)."""
        llm = self._build_llm(bind_tools=False)
        messages = self._build_messages(user_content)
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout)
        return response.content if hasattr(response, "content") else str(response)

    def set_context(self, context: dict):
        self._context = context

    async def run_with_tools(self, user_content: str, timeout: float = 120.0) -> str:
        """Run with function-calling loop: Agent can invoke tools, see results, continue."""
        import json as _json
        llm = self._build_llm(bind_tools=True)
        messages = self._build_messages(user_content)

        for round_num in range(self.max_tool_rounds):
            response = await asyncio.wait_for(llm.ainvoke(messages), timeout=timeout)
            content = response.content if hasattr(response, "content") else str(response)
            tool_calls = getattr(response, "tool_calls", []) or []

            if not tool_calls:
                return content

            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_id = tc.get("id", f"call_{round_num}_{tool_name}")

                tool = self.tool_registry.get(tool_name)
                if tool is None:
                    for t in self.tools:
                        if t.name == tool_name:
                            tool = t
                            break

                if tool:
                    result = await tool.execute(context=getattr(self, '_context', None), **tool_args)
                else:
                    result = _json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result,
                })

        logger.warning(f"Agent {self.name}: max tool rounds ({self.max_tool_rounds}) reached, returning last content")
        return messages[-1].get("content", "") if messages else ""

    async def run(
        self,
        user_content: str,
        context: dict | None = None,
        timeout: float = 120.0,
        progress_callback: callable | None = None,
    ) -> str:
        if context and self._memory:
            memory_text = self._memory.context_summary()
            if memory_text:
                user_content = f"{user_content}\n\n{memory_text}"

        if self.supports_function_calling and self.tools:
            if progress_callback:
                await progress_callback(f"{self.name} 正在使用工具调用进行分析...")
            return await self.run_with_tools(user_content, timeout)
        else:
            if progress_callback:
                await progress_callback(f"{self.name} 正在调用 LLM 进行分析...")
            return await self.run_json_mode(user_content, timeout)

    def record_memory(self, entry: dict):
        self._memory.record(entry)

    def update_model(self, model: str):
        self.model = model
        self._provider = _get_provider_for_model(model)
