"""Tool registry and Tool definition for agent tool-use."""

import json
import logging
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    category: str = "general"

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, context: dict | None = None, **kwargs) -> str:
        try:
            if context:
                args = {**context, **kwargs}
            else:
                args = kwargs
            result = await self.handler(**args)
            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            return str(result)
        except Exception as e:
            logger.error(f"Tool '{self.name}' execution failed: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (category={tool.category})")

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def get_by_category(self, category: str) -> list[Tool]:
        return [t for t in self._tools.values() if t.category == category]

    def list_for_agent(self, agent_name: str) -> list[Tool]:
        return self.get_all()


tool_registry = ToolRegistry()
