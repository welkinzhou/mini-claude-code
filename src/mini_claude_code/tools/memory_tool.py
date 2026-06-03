from __future__ import annotations


from dataclasses import dataclass

from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec
from mini_claude_code.app.context import AppContext


@dataclass(frozen=True, slots=True)
class MemoryTool:
    """管理记忆的工具"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory",
            description="Save a persistent memory that survives across sessions.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short identifier (e.g. prefer_tabs, db_schema)",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-line summary of what this memory captures",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["user", "feedback", "project", "reference"],
                        "description": "user=preferences, feedback=corrections, project=non-obvious project conventions or decision reasons, reference=external resource pointers",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full memory content (multi-line OK)",
                    },
                },
                "required": ["name", "description", "type", "content"],
            },
        )

    def run(self, tool_input: JsonObject, context: AppContext) -> str:
        name = tool_input.get("name")
        description = tool_input.get("description")
        mem_type = tool_input.get("type")
        content = tool_input.get("content")
        if not isinstance(name, str):
            return "Error: Invalid input; expected {'name': string}"
        if not isinstance(description, str):
            return "Error: Invalid input; expected {'description': string}"
        if not isinstance(mem_type, str):
            return "Error: Invalid input; expected {'type': string}"
        if not isinstance(content, str):
            return "Error: Invalid input; expected {'content': string}"
        return context.memory_manager.save_memory(name, description, mem_type, content)
