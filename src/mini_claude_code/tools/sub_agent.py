from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import JsonObject, ToolSpec
from .registry import ToolRegistry
from .runner import ToolRunner


@dataclass(frozen=True, slots=True)
class SubAgentTool:
    """Spawn a sandboxed sub-agent with a restricted tool set."""

    client: Any
    # AgentLoopConfig imported lazily to avoid circular imports at module level
    config: Any
    registry: ToolRegistry

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

    def run(self, tool_input: JsonObject) -> str:
        from mini_claude_code.core.agent import agent_loop  # avoid circular import

        task = tool_input.get("task")
        if not isinstance(task, str) or not task.strip():
            return "Error: 'task' must be a non-empty string"

        messages: list[JsonObject] = [{"role": "user", "content": task}]
        runner = ToolRunner(registry=self.registry)
        result, _ = agent_loop(
            messages=messages,
            client=self.client,
            tools=self.registry.tool_specs(),
            tool_runner=runner,
            config=self.config,
        )

        return _extract_text(result)


def _extract_text(result: Any) -> str:
    """Pull the final text content out of an agent_loop response."""
    if isinstance(result, dict) and "error" in result:
        return f"Sub-agent error: {result['error']}"

    content = getattr(result, "content", None)
    if content is None:
        return str(result)

    texts = [
        getattr(block, "text", None) for block in content if hasattr(block, "text")
    ]
    return "\n".join(t for t in texts if t) or "(no text output)"
