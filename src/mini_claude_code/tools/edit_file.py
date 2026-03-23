from __future__ import annotations

from dataclasses import dataclass

from .base import JsonObject, ToolSpec
from .path_safety import safe_path


@dataclass(frozen=True, slots=True)
class EditFileTool:

    @property
    def spec(self) -> ToolSpec:
        # 返回工具规范
        return ToolSpec(
            name="edit_file",
            description="Replace exact text in a file.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        )

    def run(self, tool_input: JsonObject) -> str:
        path = tool_input.get("path")
        old_text = tool_input.get("old_text")
        new_text = tool_input.get("new_text")
        try:
            fp = safe_path(path)
            content = fp.read_text()
            if old_text not in content:
                return f"Error: Text not found in {path}"
            fp.write_text(content.replace(old_text, new_text, 1))
            return f"Edited {path}"
        except Exception as e:
            return f"Error: {e}"
        finally:
            fp.close()
