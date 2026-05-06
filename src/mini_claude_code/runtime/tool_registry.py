from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .tool_spec import JsonObject, Tool


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    """Immutable container that maps tool name -> tool implementation."""

    tools: tuple[Tool, ...]

    @classmethod
    def from_tools(cls, tools: Iterable[Tool]) -> "ToolRegistry":
        return cls(tuple(tools))

    def tool_specs(self) -> list[JsonObject]:
        return [t.spec.to_anthropic() for t in self.tools]

    def get(self, name: str) -> Tool | None:
        for t in self.tools:
            if t.spec.name == name:
                return t
        return None
