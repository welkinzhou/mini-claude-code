from __future__ import annotations

from dataclasses import dataclass

from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec


@dataclass(frozen=True, slots=True)
class CompactTool:
    """显式触发上下文压缩的工具。

    工具本身不执行压缩，只在 ``compact_state`` 上设置 pending 标志（
    ``pending_manual = True``），由 ``after_turn`` 订阅者在本轮所有工具
    执行完毕、tool_result 回流之后统一执行压缩。
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="compact",
            description="Compact a list of messages.",
            input_schema={
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "What to preserve in the summary",
                    }
                },
            },
        )

    def run(self, tool_input: JsonObject, context) -> str:
        context.compact_state.pending_manual = True
        context.compact_state.pending_focus = tool_input.get("focus")
        return "Compressing..."
