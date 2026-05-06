from __future__ import annotations

from dataclasses import dataclass

from anthropic import Anthropic

from mini_claude_code.compact.compact import compact_history
from mini_claude_code.providers.llm import call_llm
from mini_claude_code.providers.llm.spec import LLMCaller
from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec


@dataclass(frozen=True, slots=True)
class CompactTool:
    """显式触发上下文压缩的工具。

    工具本身不持有 ``workspace`` / ``compact_state``：这些都由 ``AgentLoopContext``
    在执行时提供，工具只挂一个 after-round 钩子，让压缩落在 LLM 工具结果回流之后。
    """

    client: Anthropic
    model_id: str
    llm_call: LLMCaller = call_llm

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
        focus = tool_input.get("focus")
        client = self.client
        model_id = self.model_id
        llm_call = self.llm_call

        def _do_compact(ctx) -> None:
            print("[manual compact]")
            ctx.state.messages[:] = compact_history(
                client=client,
                messages=ctx.state.messages,
                compact_state=ctx.compact_state,
                workspace=ctx.workspace,
                llm_call=llm_call,
                focus=focus,
                model=model_id,
            )

        context.add_after_round_once(_do_compact)
        return "Compressing..."
