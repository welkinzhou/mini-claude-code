from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .hooks import HookManager
from .permission import PermissionManager
from .tool_registry import ToolRegistry
from .tool_spec import JsonObject, ToolRunContext


@dataclass(slots=True)
class ToolRunner:
    """单轮工具执行调度器。

    每个 ``tool_use`` 块按以下顺序处理：

    1. PreToolUse hook：可改写 ``tool_input``、注入 additionalContext、
       直接 block 或给出 ``permissionDecision`` 覆盖默认权限判断。
    2. PermissionManager.check：未被 hook 覆盖时按规则 + 模式 + ask 流程决策。
    3. 执行工具 ``run(tool_input, context)``，执行前后 fire ``on_tool_start``
       / ``on_tool_end`` 纯观测钩子。
    4. PostToolUse hook：可在工具执行后再次注入 additionalContext。

    additionalContext 写入 ``context.pending_messages``，由 ``after_turn``
    订阅者在本轮结束后统一 flush 为 ``user`` 消息。
    """

    registry: ToolRegistry
    on_tool_use: Callable[[str, JsonObject], None] | None = None
    permission: PermissionManager | None = None
    hooks: HookManager | None = None

    def run_from_response_content(
        self, response_content: Iterable[Any], context: ToolRunContext
    ) -> list[JsonObject]:
        """Execute tool_use blocks and return Anthropic tool_result blocks."""
        results: list[JsonObject] = []
        for block in response_content:
            response_type = getattr(block, "type", None)
            if response_type != "tool_use":
                # 文本块直接提示用户，跳过非工具块
                if response_type == "text":
                    print(block.text)
                continue

            tool_name = getattr(block, "name", None)
            raw_input = getattr(block, "input", None)
            tool_id = getattr(block, "id", None)
            if (
                not isinstance(tool_name, str)
                or not isinstance(raw_input, dict)
                or not isinstance(tool_id, str)
            ):
                continue

            # 可变副本，便于 PreToolUse hook 改写
            tool_input: JsonObject = dict(raw_input)
            print("Tool Name: ", tool_name)
            print("Tool Input: ", tool_input)

            # -- PreToolUse hook --
            permission_override: str | None = None
            if self.hooks is not None:
                hook_ctx: dict = {"tool_name": tool_name, "tool_input": tool_input}
                pre_result = self.hooks.run_hooks("PreToolUse", hook_ctx)
                tool_input = hook_ctx["tool_input"]
                self._collect_messages(context, pre_result.get("messages", []))
                if pre_result.get("blocked"):
                    reason = pre_result.get("block_reason") or "Blocked by hook"
                    results.append(
                        self._tool_result(tool_id, f"Blocked by hook: {reason}")
                    )
                    continue
                permission_override = pre_result.get("permission_override")

            # -- Permission --
            if not self._allow(tool_name, tool_input, permission_override):
                results.append(
                    self._tool_result(tool_id, "Denied by permission policy")
                )
                continue

            # -- Execute --
            tool = self.registry.get(tool_name)
            if tool is None:
                output = f"Error: Unknown tool '{tool_name}'"
            else:
                if self.on_tool_use is not None:
                    self.on_tool_use(tool_name, tool_input)
                self._fire_tool_start(context, tool_name, tool_input)
                output = tool.run(tool_input, context)
                self._fire_tool_end(context, tool_name, tool_input, output)

            # -- PostToolUse hook --
            if self.hooks is not None:
                post_ctx: dict = {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_output": output,
                }
                post_result = self.hooks.run_hooks("PostToolUse", post_ctx)
                self._collect_messages(context, post_result.get("messages", []))

            # tool_use_id 让 Anthropic 把结果与对应的工具调用关联起来
            results.append(self._tool_result(tool_id, output))

        return results

    @staticmethod
    def _tool_result(tool_id: str, content: str) -> JsonObject:
        return {"type": "tool_result", "tool_use_id": tool_id, "content": content}

    def _allow(
        self,
        tool_name: str,
        tool_input: JsonObject,
        override: str | None,
    ) -> bool:
        """根据 hook 覆盖 + PermissionManager 综合决定是否放行。"""
        if override == "allow":
            return True
        if override == "deny":
            return False
        if self.permission is None:
            return True

        decision = self.permission.check(tool_name, tool_input)
        behavior = decision.get("behavior", "ask")
        if behavior == "allow":
            return True
        if behavior == "deny":
            print(f"  [permission] DENY {tool_name}: {decision.get('reason')}")
            return False
        # ask
        return self.permission.ask_user(tool_name, tool_input)

    @staticmethod
    def _collect_messages(context: ToolRunContext, messages: list[str]) -> None:
        """把 hook 注入的文本暂存到 context.pending_messages。

        after_turn 订阅者负责把它们 flush 为 ``user`` 消息，保证写入时序
        （在本轮所有 tool_result 收集完成后再追加）。
        """
        if not messages:
            return
        pending = getattr(context, "pending_messages", None)
        if pending is None:
            return
        pending.extend(messages)

    @staticmethod
    def _fire_tool_start(
        context: ToolRunContext, tool_name: str, tool_input: JsonObject
    ) -> None:
        loop_hooks = getattr(context, "loop_hooks", None)
        if loop_hooks is not None:
            loop_hooks.fire("on_tool_start", context, tool_name, tool_input)

    @staticmethod
    def _fire_tool_end(
        context: ToolRunContext,
        tool_name: str,
        tool_input: JsonObject,
        output: str,
    ) -> None:
        loop_hooks = getattr(context, "loop_hooks", None)
        if loop_hooks is not None:
            loop_hooks.fire("on_tool_end", context, tool_name, tool_input, output)
