from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .base import JsonObject
from .registry import ToolRegistry

RoundCompleteCallback = Callable[[], None]


@dataclass(slots=True)
class ToolRunner:
    registry: ToolRegistry
    on_tool_use: Callable[[str, JsonObject], None] | None = None
    on_round_complete: list[RoundCompleteCallback] = field(default_factory=list)
    pending_compact: bool = False

    def add_round_complete_once(self, callback: RoundCompleteCallback) -> None:
        """Register a one-shot callback that removes itself after being called once."""

        def _once() -> None:
            self.on_round_complete.remove(_once)
            callback()

        self.on_round_complete.append(_once)

    def run_from_response_content(
        self, response_content: Iterable[Any]
    ) -> list[JsonObject]:
        """Execute tool_use blocks and return Anthropic tool_result blocks."""
        results: list[JsonObject] = []
        for block in response_content:
            # 如果不是工具使用块，则跳过
            response_type = getattr(block, "type", None)
            if response_type != "tool_use":
                # 文本类型给予用户提示
                if response_type == "text":
                    print(block.text)
                continue
            # 获取工具名称
            tool_name = getattr(block, "name", None)
            # 获取工具输入
            tool_input = getattr(block, "input", None)
            print("Tool Name: ", tool_name)
            print("Tool Input: ", tool_input)
            # 获取工具 ID
            # tool_use 一定会返回 id
            # Anthropic 通过这个 id 将工具结果与工具使用关联起来
            tool_id = getattr(block, "id", None)
            if (
                not isinstance(tool_name, str)
                or not isinstance(tool_input, dict)
                or not isinstance(tool_id, str)
            ):
                continue

            tool = self.registry.get(tool_name)
            if tool is None:
                output = f"Error: Unknown tool '{tool_name}'"
            else:
                if self.on_tool_use is not None:
                    self.on_tool_use(tool_name, tool_input)
                output = tool.run(tool_input, self)
            # 将工具结果添加到结果列表
            # tool_use_id 告诉 Anthropic 这个结果是哪个工具使用的
            results.append(
                {"type": "tool_result", "tool_use_id": tool_id, "content": output}
            )

        for cb in list(self.on_round_complete):
            cb()
        return results
