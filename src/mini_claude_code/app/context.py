from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mini_claude_code.compact.compact import CompactState
from mini_claude_code.domain.usage import UsageCalculator
from mini_claude_code.infra.llm_logger import LLMCallLogger
from mini_claude_code.providers.skills import SkillLoader
from mini_claude_code.runtime.hooks import HookManager
from mini_claude_code.runtime.loop import AgentLoopConfig
from mini_claude_code.runtime.permission import PermissionManager

from .config import AppConfig
from .workspace import WorkspacePaths


@dataclass(slots=True)
class AppContext:
    """聚合所有由 ``app.bootstrap`` 装配出来的会话级依赖。

    上层组件（cli / runtime / tools）应只读取此对象，而不是在自己的模块中
    重复实例化 ``Config`` / ``LLMCallLogger`` 等。
    """

    config: AppConfig
    workspace: WorkspacePaths
    client: Any  # anthropic.Anthropic（弱类型避免上层强依赖）
    llm_logger: LLMCallLogger
    skill_loader: SkillLoader
    permission: PermissionManager
    hooks: HookManager
    usage: UsageCalculator
    compact_state: CompactState
    main_loop_config: AgentLoopConfig
    sub_loop_config: AgentLoopConfig
