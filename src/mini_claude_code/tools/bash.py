from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec


@dataclass(frozen=True, slots=True)
class BashTool:
    """Run a shell command.

    Note: 危险命令拦截已统一交给 ``runtime.permission.PermissionManager`` 与
    ``BashSecurityValidator`` 处理，本工具不再自带黑名单，避免规则分叉。
    """

    timeout_s: int = 120
    max_output_chars: int = 50_000

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="bash",
            description="Run a shell command.",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

    def run(self, tool_input: JsonObject, _context=None) -> str:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return "Error: Invalid input; expected {'command': string}"

        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_s,
            )
            out = (r.stdout + r.stderr).strip()
            return out[: self.max_output_chars] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Timeout ({self.timeout_s}s)"
