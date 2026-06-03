from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

JsonObject = dict[str, Any]


@runtime_checkable
class ToolRunContext(Protocol):
    """工具运行期能拿到的最小上下文。

    放在 runtime 层，使工具可以读 ``state`` / ``compact_state``，
    而无需反向 import core / app 层。
    """

    state: Any
    compact_state: Any


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A JSON-schema tool spec compatible with Anthropic tool calling."""

    name: str
    description: str
    input_schema: JsonObject
    input_examples: list[JsonObject] | None = None

    def to_anthropic(self) -> JsonObject:
        spec: JsonObject = {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
        if self.input_examples:
            spec["input_examples"] = self.input_examples
        return spec


class Tool(Protocol):
    """Tool 协议：只要拥有 ``spec`` 与 ``run`` 方法即可被注册。"""

    spec: ToolSpec

    def run(
        self, tool_input: JsonObject, context: ToolRunContext | None = None
    ) -> str: ...
