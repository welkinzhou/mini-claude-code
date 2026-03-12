from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .base import JsonObject
from .registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class ToolRunner:
    registry: ToolRegistry
    on_tool_use: Callable[[str, JsonObject], None] | None = None

    def run_from_response_content(self, response_content: Iterable[Any]) -> list[JsonObject]:
        """Execute tool_use blocks and return Anthropic tool_result blocks."""
        results: list[JsonObject] = []
        for block in response_content:
            # 如果不是工具使用块，则跳过
            if getattr(block, "type", None) != "tool_use":
                continue
            # 获取工具名称
            tool_name = getattr(block, "name", None)
            # 获取工具输入
            tool_input = getattr(block, "input", None)
            # 获取工具 ID
            # tool_use 一定会返回 id
            # Anthropic 通过这个 id 将工具结果与工具使用关联起来
            tool_id = getattr(block, "id", None)

            if not isinstance(tool_name, str) or not isinstance(tool_input, dict) or not isinstance(tool_id, str):
                continue

            tool = self.registry.get(tool_name)
            if tool is None:
                output = f"Error: Unknown tool '{tool_name}'"
            else:
                if self.on_tool_use is not None:
                    self.on_tool_use(tool_name, tool_input)
                output = tool.run(tool_input)
            # 将工具结果添加到结果列表
            # tool_use_id 告诉 Anthropic 这个结果是哪个工具使用的
            results.append({"type": "tool_result", "tool_use_id": tool_id, "content": output})
        return results

