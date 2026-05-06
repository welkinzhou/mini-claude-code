from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path

from mini_claude_code.app.workspace import WorkspacePaths


# 工作模式
MODES = ("default", "plan", "auto")
# 只读工具，无需权限管理
READ_ONLY_TOOLS = {"read_file", "bash_readonly"}
# 可写工具，需要权限管理
WRITE_TOOLS = {"write_file", "edit_file", "bash"}


# -- Bash 命令过滤 --
class BashSecurityValidator:
    """Bash 命令安全检测器。

    Bash 权限很大，几乎能做任何事；危险动作必须做规则化拦截。
    Plan 模式下只允许做计划，不进行写操作 —— 由上层 PermissionManager 负责该控制。
    """

    VALIDATORS = [
        # python 正则表达式语法解析:
        # r"[;&|`$]" 匹配 [;&|`$] 中的任意字符；\b 单词边界；\s 空白字符。
        ("shell_metachar", r"[;&|`$]"),  # shell 元字符
        ("sudo", r"\bsudo\b"),  # 超级管理权限
        ("rm_rf", r"\brm\s+(-[a-zA-Z]*)?r"),  # 递归删除
        ("cmd_substitution", r"\$\("),  # 命令替换
        ("ifs_injection", r"\bIFS\s*="),  # IFS 注入
    ]

    def validate(self, command: str) -> list:
        """返回校验失败的规则列表，每个元素是 ``(name, pattern)``。"""
        failures = []
        for name, pattern in self.VALIDATORS:
            if re.search(pattern, command):
                failures.append((name, pattern))
        return failures

    def is_safe(self, command: str) -> bool:
        return len(self.validate(command)) == 0

    def describe_failures(self, command: str) -> str:
        failures = self.validate(command)
        if not failures:
            return "No issues detected"
        parts = [f"{name} (pattern: {pattern})" for name, pattern in failures]
        return "Security flags: " + ", ".join(parts)


def is_workspace_trusted(workspace: WorkspacePaths) -> bool:
    """通过 ``.claude/.claude_trusted`` 标记文件判断工作区是否可信。"""
    return workspace.trust_marker.exists()


# -- Permission 规则 --
# 规则检查顺序：第一个匹配的规则获胜
# Format: {"tool": "<tool_name_or_*>", "path": "<glob_or_*>", "behavior": "allow|deny|ask"}
DEFAULT_RULES = [
    {"tool": "bash", "content": "rm -rf /", "behavior": "deny"},
    {"tool": "bash", "content": "sudo *", "behavior": "deny"},
    {"tool": "read_file", "path": "*", "behavior": "allow"},
]


class PermissionManager:
    """工具调用前的权限决策器。

    Pipeline: ``deny_rules → mode_check → allow_rules → ask_user``。

    构造函数注入 ``WorkspacePaths`` 与可选的初始规则列表，模块本身不再持有
    任何全局状态。
    """

    def __init__(
        self,
        workspace: WorkspacePaths,
        mode: str = "default",
        rules: list | None = None,
        bash_validator: BashSecurityValidator | None = None,
    ):
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}. Choose from {MODES}")
        self.workspace = workspace
        self.mode = mode
        self.rules = rules or list(DEFAULT_RULES)
        self.bash_validator = bash_validator or BashSecurityValidator()
        # 简单的连续拒绝跟踪，用于在用户多次拒绝时给出提示
        self.consecutive_denials = 0
        self.max_consecutive_denials = 3

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}. Choose from {MODES}")
        self.mode = mode

    def check(self, tool_name: str, tool_input: dict) -> dict:
        """Returns: ``{"behavior": "allow"|"deny"|"ask", "reason": str}``."""
        # Step 0: 单独检测 Bash 命令
        if tool_name == "bash":
            command = tool_input.get("command", "")
            failures = self.bash_validator.validate(command)
            if failures:
                severe = {"sudo", "rm_rf"}
                severe_hits = [f for f in failures if f[0] in severe]
                desc = self.bash_validator.describe_failures(command)
                if severe_hits:
                    return {"behavior": "deny", "reason": f"Bash validator: {desc}"}
                return {"behavior": "ask", "reason": f"Bash validator flagged: {desc}"}

        # Step 1: deny 规则不可绕过
        for rule in self.rules:
            if rule["behavior"] != "deny":
                continue
            if self._matches(rule, tool_name, tool_input):
                return {"behavior": "deny", "reason": f"Blocked by deny rule: {rule}"}

        # Step 2: mode 规则
        if self.mode == "plan":
            if tool_name in WRITE_TOOLS:
                return {
                    "behavior": "deny",
                    "reason": "Plan mode: write operations are blocked",
                }
            return {"behavior": "allow", "reason": "Plan mode: read-only allowed"}

        if self.mode == "auto":
            if tool_name in READ_ONLY_TOOLS or tool_name == "read_file":
                return {
                    "behavior": "allow",
                    "reason": "Auto mode: read-only tool auto-approved",
                }
            # auto 模式下写操作走 allow rules → ask 流程

        # Step 3: allow 规则
        for rule in self.rules:
            if rule["behavior"] != "allow":
                continue
            if self._matches(rule, tool_name, tool_input):
                self.consecutive_denials = 0
                return {"behavior": "allow", "reason": f"Matched allow rule: {rule}"}

        # Step 4: 询问用户
        return {
            "behavior": "ask",
            "reason": f"No rule matched for {tool_name}, asking user",
        }

    def ask_user(self, tool_name: str, tool_input: dict) -> bool:
        """交互式批准提示。返回 True 表示批准。"""
        preview = json.dumps(tool_input, ensure_ascii=False)[:200]
        print(f"\n  [Permission] {tool_name}: {preview}")
        try:
            answer = input("  Allow? (y/n/always): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False

        if answer == "always":
            self.rules.append({"tool": tool_name, "path": "*", "behavior": "allow"})
            self.consecutive_denials = 0
            return True
        if answer in ("y", "yes"):
            self.consecutive_denials = 0
            return True

        self.consecutive_denials += 1
        if self.consecutive_denials >= self.max_consecutive_denials:
            print(
                f"  [{self.consecutive_denials} consecutive denials -- "
                "consider switching to plan mode]"
            )
        return False

    def _matches(self, rule: dict, tool_name: str, tool_input: dict) -> bool:
        if rule.get("tool") and rule["tool"] != "*":
            if rule["tool"] != tool_name:
                return False
        if "path" in rule and rule["path"] != "*":
            path = tool_input.get("path", "")
            if not fnmatch(path, rule["path"]):
                return False
        if "content" in rule:
            command = tool_input.get("command", "")
            if not fnmatch(command, rule["content"]):
                return False
        return True
