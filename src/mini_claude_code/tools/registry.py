from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .base import JsonObject, Tool


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    tools: tuple[Tool, ...]

    @classmethod
    def from_tools(cls, tools: Iterable[Tool]) -> "ToolRegistry":
        return cls(tuple(tools))

    def tool_specs(self) -> list[JsonObject]:
        # 将工具规范转换为 Anthropic 格式
        return [t.spec.to_anthropic() for t in self.tools]

    def get(self, name: str) -> Tool | None:
        for t in self.tools:
            if t.spec.name == name:
                return t
        return None

