from __future__ import annotations

from dataclasses import dataclass
from mini_claude_code.infra.paths import safe_path

from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec


@dataclass(frozen=True, slots=True)
class WriteFileTool:

    @property
    def spec(self) -> ToolSpec:
        # 返回工具规范
        return ToolSpec(
            name="write_file",
            description="Write content to a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["path", "text"],
            },
        )

    def run(self, tool_input: JsonObject, _context=None) -> str:
        path = tool_input.get("path")
        text = tool_input.get("text")
        try:
            fp = safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(text)
            return f"Wrote {len(text)} characters to {path}"
        except Exception as e:
            return f"Error: {e}"
