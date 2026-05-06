from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mini_claude_code.app.workspace import WorkspacePaths
from mini_claude_code.compact.compact import (
    CompactState,
    compact_history,
    micro_compact,
)
from mini_claude_code.domain.messages import normalize_messages
from mini_claude_code.domain.state import LoopState
from mini_claude_code.domain.usage import UsageCalculator
from mini_claude_code.infra.llm_logger import LLMCallLogger
from mini_claude_code.providers.llm import call_llm
from mini_claude_code.providers.llm.spec import LLMCaller

from .hooks import HookManager
from .tool_runner import ToolRunner


JsonObject = dict[str, Any]

THRESHOLD = 50000


@dataclass(frozen=True, slots=True)
class AgentLoopConfig:
    """Agent loop 静态配置。"""

    model: str
    system: str
    max_tokens: int = 8000


AfterRoundHook = Callable[["AgentLoopContext"], None]


@dataclass
class AgentLoopContext:
    """Agent loop 运行期上下文，承载注入依赖与可拓展钩子。"""

    state: LoopState
    client: Any
    config: AgentLoopConfig
    tool_runner: ToolRunner
    workspace: WorkspacePaths
    compact_state: CompactState
    llm_logger: LLMCallLogger
    llm_call: LLMCaller
    usage: UsageCalculator
    after_round_hooks: list[AfterRoundHook] = field(default_factory=list)

    def add_after_round(self, cb: AfterRoundHook) -> None:
        """添加一个 after-round 钩子。"""
        self.after_round_hooks.append(cb)

    def add_after_round_once(self, cb: AfterRoundHook) -> None:
        """添加一个只触发一次的 after-round 钩子。"""

        def _once(ctx: "AgentLoopContext") -> None:
            self.after_round_hooks.remove(_once)
            cb(ctx)

        self.after_round_hooks.append(_once)

    def fire_after_round(self) -> None:
        """逐个触发已注册的 after-round 钩子。"""
        for cb in list(self.after_round_hooks):
            cb(self)


def estimate_tokens(messages: list) -> int:
    """Rough token count: ~4 chars per token."""
    return len(str(messages)) // 4


def run_one_turn(
    *,
    context: AgentLoopContext,
    tools: list[JsonObject],
    call_id: str,
) -> bool:
    """执行一轮 LLM 调用，返回是否继续循环。"""
    state = context.state
    config = context.config
    tool_runner = context.tool_runner
    client = context.client
    llm_logger = context.llm_logger
    usage = context.usage

    messages = state.messages
    # 简单压缩消息：陈旧 tool_result 替换成占位符
    # notice：压缩会破坏 prompt 缓存，后续可在这里做更精细的策略
    micro_compact(messages)
    if estimate_tokens(messages) > THRESHOLD:
        print("[窗口即将溢出，自动压缩]")
        # llm 总结压缩，使用 json 格式总结 message，无需 normalize
        messages[:] = compact_history(
            client,
            messages,
            compact_state=context.compact_state,
            workspace=context.workspace,
            llm_call=context.llm_call,
            model=config.model,
        )

    try:
        llm_logger.log_request(
            call_id=call_id,
            model=config.model,
            system=config.system,
            messages=messages,
            tools=tools,
            max_tokens=config.max_tokens,
        )
        response = context.llm_call(
            client=client,
            model=config.model,
            system=config.system,
            messages=normalize_messages(messages),
            tools=tools,
            max_tokens=config.max_tokens,
        )
        llm_logger.log_response(call_id=call_id, response=response)
    except Exception as e:
        llm_logger.log_error(call_id=call_id, error=e)
        err_msg = getattr(e, "message", None) or str(e)
        print(f"\033[31mllm error: {err_msg}\033[0m")  # 红色错误输出
        # 不让程序结束：直接结束本次 agent_loop，让 cli 回到下一轮输入
        state.transition_reason = "llm_error"
        return False

    # 记录本轮 token 用量（按 state.session_id 分桶，内部判断会话切换）
    if state.session_id is not None:
        u = response.usage
        usage.add(
            state.session_id,
            {
                "input_tokens": getattr(u, "input_tokens", 0),
                "output_tokens": getattr(u, "output_tokens", 0),
                "cache_creation_input_tokens": getattr(
                    u, "cache_creation_input_tokens", 0
                ),
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0),
            },
        )

    messages.append({"role": "assistant", "content": response.content})

    # 不是工具调用，说明模型认为任务完成
    if response.stop_reason != "tool_use":
        state.turn_count += 1
        state.transition_reason = None
        return False

    results = tool_runner.run_from_response_content(response.content, context)
    messages.append({"role": "user", "content": results})

    state.turn_count += 1
    state.transition_reason = "tool_result"
    return True


def agent_loop(
    *,
    state: LoopState,
    client: Any,
    tools: list[JsonObject],
    tool_runner: ToolRunner,
    config: AgentLoopConfig,
    workspace: WorkspacePaths,
    compact_state: CompactState,
    llm_logger: LLMCallLogger,
    usage: UsageCalculator,
    llm_call: LLMCaller = call_llm,
    hooks: HookManager | None = None,
) -> Any:
    """Agent 主循环：反复请求 LLM 并执行工具直到模型停止调用工具。

    所有依赖通过参数注入；``app.bootstrap`` 是唯一允许构造它们的地方。
    若调用方提供 ``hooks``，会在循环开始前触发一次 ``SessionStart``，并把
    返回的 additionalContext 文本作为 ``user`` 消息插入到对话最前面，让模型
    在第一次 LLM 调用时就能看到。

    Anthropic tool_use 响应结构（节选）::

        {
            "id": "msg_abc",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "..."},
                {"type": "tool_use", "id": "toolu_123", "name": "...", "input": {}}
            ],
            "stop_reason": "tool_use"
        }
    """
    context = AgentLoopContext(
        state=state,
        client=client,
        config=config,
        tool_runner=tool_runner,
        workspace=workspace,
        compact_state=compact_state,
        llm_logger=llm_logger,
        llm_call=llm_call,
        usage=usage,
    )

    # SessionStart hook：让外部脚本能在每次新任务开始时注入背景信息
    if hooks is not None:
        session_result = hooks.run_hooks("SessionStart", {})
        for text in session_result.get("messages", []):
            state.messages.append(
                {"role": "user", "content": f"[session start]\n{text}"}
            )

    call_id = llm_logger.new_call_id()

    while run_one_turn(context=context, tools=tools, call_id=call_id):
        context.fire_after_round()

    context.fire_after_round()
    return state.messages
