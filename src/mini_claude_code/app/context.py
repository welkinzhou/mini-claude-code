from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mini_claude_code.compact.compact import CompactState
from mini_claude_code.domain.config import AppConfig
from mini_claude_code.domain.usage import UsageCalculator
from mini_claude_code.domain.workspace import WorkspacePaths
from mini_claude_code.infra.llm_logger import LLMCallLogger
from mini_claude_code.providers.skills import SkillLoader
from mini_claude_code.runtime.hooks import HookManager
from mini_claude_code.runtime.loop import AgentLoopConfig, LoopHooks
from mini_claude_code.runtime.permission import PermissionManager
from mini_claude_code.runtime.memory import MemoryManager


@dataclass(slots=True)
class AppContext:
    """聚合所有由 ``app.bootstrap`` 装配出来的会话级依赖。

    上层组件（cli / runtime / tools）应只读取此对象，而不是在自己的模块中
    重复实例化 ``Config`` / ``LLMCallLogger`` 等。

    App 级生命周期钩子
    ------------------
    - ``on_startup``：REPL 开始前触发一次。签名：``Callable[[AppContext], None]``
    - ``on_shutdown``：REPL 正常退出或异常退出时触发一次（``finally`` 块）。
    """

    config: AppConfig
    workspace: WorkspacePaths
    client: Any  # anthropic.Anthropic（弱类型避免上层强依赖）
    llm_logger: LLMCallLogger
    skill_loader: SkillLoader
    memory_manager: MemoryManager
    permission: PermissionManager
    hooks: HookManager
    usage: UsageCalculator
    compact_state: CompactState
    main_loop_config: AgentLoopConfig
    sub_loop_config: AgentLoopConfig
    loop_hooks: LoopHooks
    on_startup: list[Callable[[AppContext], None]] = field(default_factory=list)
    on_shutdown: list[Callable[[AppContext], None]] = field(default_factory=list)
