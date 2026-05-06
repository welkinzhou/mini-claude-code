from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Protocol

from mini_claude_code.app.workspace import WorkspacePaths


HOOK_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart")
HOOK_TIMEOUT = 30  # seconds


class HookRunner(Protocol):
    def run(self, event_name: str, payload: dict) -> dict: ...


class HookManager:
    """加载 ``.hooks.json`` 并执行匹配命令。

    主要做三件事：
    - 加载 hooks 配置；
    - 根据事件 / matcher 执行命令；
    - 聚合阻塞 / 注入消息 / 权限覆盖等结果。

    .hooks.json 格式：

    .. code-block:: json

        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "bash",
                        "command": "echo 'PreToolUse'"
                    }
                ]
            }
        }
    """

    def __init__(
        self,
        workspace: WorkspacePaths,
        config_path: Path | None = None,
        sdk_mode: bool = False,
    ):
        self.workspace = workspace
        self.hooks: dict[str, list] = {
            "PreToolUse": [],
            "PostToolUse": [],
            "SessionStart": [],
        }
        self._sdk_mode = sdk_mode

        config_path = config_path or workspace.hooks_config
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                for event in HOOK_EVENTS:
                    self.hooks[event] = config.get("hooks", {}).get(event, [])
                print(f"[Hooks loaded from {config_path}]")
            except Exception as e:
                print(f"[Hook config error: {e}]")

    def _check_workspace_trust(self) -> bool:
        """SDK 模式默认可信；否则要求 ``.claude_trusted`` 标记存在。"""
        if self._sdk_mode:
            return True
        return self.workspace.trust_marker.exists()

    def run_hooks(self, event: str, context: dict | None = None) -> dict:
        """执行所有 hooks，返回聚合结果。

        Returns
        -------
        ``{"blocked": bool, "messages": list[str], ...}``
            - ``blocked``: 任意 hook 以 exit code 1 结束时为 ``True``
            - ``messages``: 来自 exit code 2 的 stderr 内容（注入到对话）
            - ``permission_override``: hook 通过 stdout JSON 提交的权限决策
            - ``block_reason``: 拦截原因（如有）
        """
        result: dict = {"blocked": False, "messages": []}

        if not self._check_workspace_trust():
            return result

        hooks = self.hooks.get(event, [])

        for hook_def in hooks:
            matcher = hook_def.get("matcher")
            if matcher and context:
                tool_name = context.get("tool_name", "")
                if matcher != "*" and matcher != tool_name:
                    continue

            command = hook_def.get("command", "")
            if not command:
                continue

            env = dict(os.environ)
            if context:
                env["HOOK_EVENT"] = event
                env["HOOK_TOOL_NAME"] = context.get("tool_name", "")
                env["HOOK_TOOL_INPUT"] = json.dumps(
                    context.get("tool_input", {}), ensure_ascii=False
                )[:10000]
                if "tool_output" in context:
                    env["HOOK_TOOL_OUTPUT"] = str(context["tool_output"])[:10000]

            try:
                r = subprocess.run(
                    command,
                    shell=True,
                    check=False,
                    cwd=self.workspace.work_path,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=HOOK_TIMEOUT,
                )

                if r.returncode == 0:
                    if r.stdout.strip():
                        print(f"  [hook:{event}] {r.stdout.strip()[:100]}")

                    try:
                        hook_output = json.loads(r.stdout)
                        if "updatedInput" in hook_output and context:
                            context["tool_input"] = hook_output["updatedInput"]
                        if "additionalContext" in hook_output:
                            result["messages"].append(hook_output["additionalContext"])
                        if "permissionDecision" in hook_output:
                            result["permission_override"] = hook_output[
                                "permissionDecision"
                            ]
                    except (json.JSONDecodeError, TypeError):
                        pass  # stdout was not JSON -- normal for simple hooks

                elif r.returncode == 1:
                    result["blocked"] = True
                    reason = r.stderr.strip() or "Blocked by hook"
                    result["block_reason"] = reason
                    print(f"  [hook:{event}] BLOCKED: {reason[:200]}")

                elif r.returncode == 2:
                    msg = r.stderr.strip()
                    if msg:
                        result["messages"].append(msg)
                        print(f"  [hook:{event}] INJECT: {msg[:200]}")

            except subprocess.TimeoutExpired:
                print(f"  [hook:{event}] Timeout ({HOOK_TIMEOUT}s)")
            except Exception as e:
                print(f"  [hook:{event}] Error: {e}")

        return result
