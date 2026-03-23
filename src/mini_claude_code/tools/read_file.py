from __future__ import annotations

from dataclasses import dataclass

from .base import JsonObject, ToolSpec
from .path_safety import safe_path


@dataclass(frozen=True, slots=True)
class ReadFileTool:
    # 最大读取字符数，默认50000字符
    max_output_chars: int = 50_000

    @property
    def spec(self) -> ToolSpec:
        # 返回工具规范
        return ToolSpec(
            name="read_file",
            description="Read a file and return the content.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["path"],
            },
        )

    def run(self, tool_input: JsonObject) -> str:
        path = tool_input.get("path")
        limit = tool_input.get("limit")
        try:
            text = safe_path(path).read_text()
            lines = text.splitlines()
            if limit and limit < len(lines):
                lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
            return "\n".join(lines)[: self.max_output_chars]
        except Exception as e:
            return f"Error: {e}"
