from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mini_claude_code.app.workspace import WorkspacePaths
from mini_claude_code.compact.compact import CompactState
from mini_claude_code.domain.state import LoopState, generate_session_id
from mini_claude_code.domain.usage import UsageCalculator
from mini_claude_code.infra.llm_logger import LLMCallLogger
from mini_claude_code.runtime.hooks import HookManager
from mini_claude_code.runtime.loop import agent_loop
from mini_claude_code.runtime.permission import PermissionManager
from mini_claude_code.runtime.tool_registry import ToolRegistry
from mini_claude_code.runtime.tool_runner import ToolRunner
from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec


@dataclass(frozen=True, slots=True)
class SubAgentTool:
    """Spawn a sandboxed sub-agent with a restricted tool set.

    依赖通过构造函数注入，工具运行期不再做任何 lazy import。
    子 agent 与主 agent 共享 ``permission`` / ``hooks`` / ``llm_logger`` /
    ``usage``，但 ``LoopState`` 与 ``CompactState`` 都是新建的。
    """

    client: Any
    config: Any  # AgentLoopConfig：保持弱类型避免循环 import
    registry: ToolRegistry
    workspace: WorkspacePaths
    llm_logger: LLMCallLogger
    usage: UsageCalculator
    permission: PermissionManager | None = None
    hooks: HookManager | None = None

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sub_agent",
            description=(
                "Delegate a focused sub-task to a sandboxed agent that has access "
                "to a restricted set of tools. "
                "Use this when you want to isolate a research or analysis step."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task description for the sub-agent.",
                    }
                },
                "required": ["task"],
            },
        )

    def run(self, tool_input: JsonObject, _context=None) -> str:
        task = tool_input.get("task")
        if not isinstance(task, str) or not task.strip():
            return "Error: 'task' must be a non-empty string"

        messages: list[JsonObject] = [{"role": "user", "content": task}]
        runner = ToolRunner(
            registry=self.registry,
            permission=self.permission,
            hooks=self.hooks,
        )
        # 子 agent 使用独立的 session_id，usage 会把它当成新任务统计
        state = LoopState(messages=messages, session_id=generate_session_id())

        result = agent_loop(
            state=state,
            client=self.client,
            config=self.config,
            tools=self.registry.tool_specs(),
            tool_runner=runner,
            workspace=self.workspace,
            compact_state=CompactState(),
            llm_logger=self.llm_logger,
            usage=self.usage,
            hooks=self.hooks,
        )

        return _extract_text(result)


def _extract_text(result: Any) -> str:
    """Pull the final text content out of an ``agent_loop`` response."""
    if isinstance(result, dict) and "error" in result:
        return f"Sub-agent error: {result['error']}"

    content = getattr(result, "content", None)
    if content is None:
        return str(result)

    texts = [
        getattr(block, "text", None) for block in content if hasattr(block, "text")
    ]
    return "\n".join(t for t in texts if t) or "(no text output)"
