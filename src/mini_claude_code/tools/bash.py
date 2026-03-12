from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any

from .base import JsonObject, ToolSpec


@dataclass(frozen=True, slots=True)
class BashTool:
    # 超时时间，默认120秒
    timeout_s: int = 120
    # 最大输出字符数，默认50000字符
    max_output_chars: int = 50_000

    @property
    def spec(self) -> ToolSpec:
        # 返回工具规范
        return ToolSpec(
            name="bash",
            description="Run a shell command.",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

    def run(self, tool_input: JsonObject) -> str:
        # 获取命令
        command = tool_input.get("command")
        if not isinstance(command, str):
            return "Error: Invalid input; expected {'command': string}"
        # 危险命令
        dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
        if any(d in command for d in dangerous):
            return "Error: Dangerous command blocked"

        try:
            # 执行命令
            r = subprocess.run(
                command,
                shell=True,
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
            # 获取输出，标准输出加错误输出
            out = (r.stdout + r.stderr).strip()
            # 返回输出，如果输出为空，返回 "(no output)"
            # 截取最大输出字符数
            return out[: self.max_output_chars] if out else "(no output)"
        # 超时错误
        except subprocess.TimeoutExpired:
            # 返回超时错误
            return f"Error: Timeout ({self.timeout_s}s)"

