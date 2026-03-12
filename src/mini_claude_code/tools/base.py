from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A JSON-schema tool spec compatible with Anthropic tool calling."""

    name: str
    description: str
    input_schema: JsonObject

    def to_anthropic(self) -> JsonObject:
        # 将工具规范转换为 Anthropic 格式
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

# Protocol 协议类型
# 定义了 Tool 接口，用于定义工具的规范
# 只要有 spec: ToolSpec 属性，
# 并且有 run(self, tool_input: JsonObject) -> str 方法
# 就被视为符合 Tool 类型，不需要显式继承 Tool
class Tool(Protocol):
    spec: ToolSpec

    def run(self, tool_input: JsonObject) -> str: ...

