"""唯一允许做装配 / 副作用的层。

凡是涉及读环境、读磁盘、构造长寿命单例的工作都集中在这里完成；
其它模块只接收已经准备好的 ``AppContext``，不再各自 ``Path.cwd()``。
"""

from __future__ import annotations

from typing import Any, Callable

from dotenv import find_dotenv, load_dotenv, set_key

from mini_claude_code.compact.compact import CompactState, compact_history
from mini_claude_code.domain.config import AppConfig
from mini_claude_code.domain.usage import UsageCalculator
from mini_claude_code.domain.workspace import WorkspacePaths
from mini_claude_code.infra.llm_logger import LLMCallLogger
from mini_claude_code.providers.llm import call_llm
from mini_claude_code.providers.llm.anthropic import create_anthropic_client
from mini_claude_code.providers.skills import SkillLoader
from mini_claude_code.runtime.hooks import HookManager
from mini_claude_code.runtime.loop import AgentLoopConfig, AgentLoopContext, LoopHooks
from mini_claude_code.runtime.permission import PermissionManager
from mini_claude_code.runtime.tool_registry import ToolRegistry
from mini_claude_code.runtime.tool_runner import ToolRunner
from mini_claude_code.runtime.tool_spec import JsonObject
from mini_claude_code.tools.bash import BashTool
from mini_claude_code.tools.compact_tool import CompactTool
from mini_claude_code.tools.edit_file import EditFileTool
from mini_claude_code.tools.load_skill import LoadSkillTool
from mini_claude_code.tools.read_file import ReadFileTool
from mini_claude_code.tools.sub_agent import SubAgentTool
from mini_claude_code.tools.task import TaskManager, TaskTool
from mini_claude_code.tools.write_file import WriteFileTool
from mini_claude_code.runtime.memory import MemoryManager

from mini_claude_code.runtime.prompt import SystemPromptBuilder

from .context import AppContext


def _make_compact_after_turn(
    client: Any,
    model_id: str,
) -> Callable[[AgentLoopContext], None]:
    """构造工具触发压缩的 after_turn 订阅者。

    检查 ``compact_state.pending_manual``，若为真则执行 LLM 压缩并重置标志。
    """

    def _compact(ctx: AgentLoopContext) -> None:
        if not ctx.compact_state.pending_manual:
            return
        ctx.compact_state.pending_manual = False
        focus = ctx.compact_state.pending_focus
        ctx.compact_state.pending_focus = None
        print("[manual compact]")
        ctx.state.messages[:] = compact_history(
            client=client,
            messages=ctx.state.messages,
            compact_state=ctx.compact_state,
            workspace=ctx.workspace,
            llm_call=call_llm,
            focus=focus,
            model=model_id,
        )

    return _compact


def _flush_pending_messages(ctx: AgentLoopContext) -> None:
    """after_turn 订阅者：把 hook 注入的消息 flush 为 user 消息。"""
    if not ctx.pending_messages:
        return
    for text in ctx.pending_messages:
        ctx.state.messages.append(
            {
                "role": "user",
                "content": f"[hook context]\n{text}",
            }
        )
    ctx.pending_messages.clear()


def build_loop_hooks(client: Any, model_id: str) -> LoopHooks:
    """构造默认 ``LoopHooks``，注册内置 after_turn 订阅者。

    执行顺序：
    1. compact 订阅者（检查 pending_manual）
    2. 消息注入订阅者（flush pending_messages）
    """
    hooks = LoopHooks()
    hooks.after_turn.append(_make_compact_after_turn(client, model_id))
    hooks.after_turn.append(_flush_pending_messages)
    return hooks


def load_app_config() -> AppConfig:
    """加载 .env 并构造 ``AppConfig``。幂等，可多次调用。

    所有需要在 bootstrap 之前读取 env 的调用方（例如 cli 决定 mode 时）
    都应走这里，而不是自行 ``load_dotenv`` / ``os.getenv``。
    """
    load_dotenv(override=True)
    return AppConfig.from_env()


def persist_env_var(key: str, value: str) -> bool:
    """把 ``key=value`` 持久化回项目的 .env 文件。

    返回 True 表示已写入，False 表示找不到 .env 文件。IO 副作用集中在 app 层，
    避免上层（cli / runtime）直接依赖 dotenv。
    """
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        return False
    set_key(dotenv_path, key, value)
    return True


def build_app_context(
    mode: str = "default",
    *,
    max_tokens: int = 8000,
    config: AppConfig | None = None,
) -> AppContext:
    """构造所有会话级依赖，返回一个完全装配好的 ``AppContext``。

    ``config`` 已就绪时直接复用，避免重复 ``load_dotenv``；否则内部走
    ``load_app_config()``。这是整个项目里唯一允许产生 import-time 副作用的地方。
    """
    if config is None:
        config = load_app_config()
    workspace = WorkspacePaths.from_cwd()
    workspace.logs_dir.mkdir(parents=True, exist_ok=True)

    client = create_anthropic_client(config)
    model_id = config.require_model_id()

    llm_logger = LLMCallLogger(workspace.llm_call_log)
    skill_loader = SkillLoader(workspace.skills_dir)
    permission = PermissionManager(workspace=workspace, mode=mode)
    hooks = HookManager(workspace=workspace)
    usage = UsageCalculator()
    compact_state = CompactState()
    loop_hooks = build_loop_hooks(client, model_id)

    memory_manager = MemoryManager(workspace.memories_dir)

    system_prompt_builder = SystemPromptBuilder(workspace, skill_loader, memory_manager)

    main_loop_config = AgentLoopConfig(
        model=model_id,
        system=system_prompt_builder.buildSystemPrompt(),
        max_tokens=max_tokens,
    )
    sub_loop_config = AgentLoopConfig(
        model=model_id,
        system=system_prompt_builder.buildSubagentSystemPrompt(),
        max_tokens=max_tokens,
    )

    return AppContext(
        config=config,  # 模型等配置项
        workspace=workspace,  # 工作区路径
        client=client,
        llm_logger=llm_logger,  # 日志记录
        skill_loader=skill_loader,  # skill 加载
        permission=permission,
        hooks=hooks,
        usage=usage,
        compact_state=compact_state,
        main_loop_config=main_loop_config,
        sub_loop_config=sub_loop_config,
        loop_hooks=loop_hooks,
        memory_manager=memory_manager,
    )


def build_subagent_registry(ctx: AppContext) -> ToolRegistry:
    """子 agent 的受限工具集（只能读写 / 跑命令）。"""
    return ToolRegistry.from_tools(
        [ReadFileTool(), BashTool(), WriteFileTool(), EditFileTool()]
    )


def build_main_registry(ctx: AppContext) -> ToolRegistry:
    """主 agent 的完整工具集，包含 sub_agent / compact / task / load_skill。"""
    sub_registry = build_subagent_registry(ctx)
    sub_agent_tool = SubAgentTool(
        client=ctx.client,
        config=ctx.sub_loop_config,
        registry=sub_registry,
        workspace=ctx.workspace,
        llm_logger=ctx.llm_logger,
        usage=ctx.usage,
        permission=ctx.permission,
        hooks=ctx.hooks,
    )
    task_manager = TaskManager(ctx.workspace.tasks_dir)
    return ToolRegistry.from_tools(
        [
            BashTool(),
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            LoadSkillTool(skill_loader=ctx.skill_loader),
            sub_agent_tool,
            TaskTool(task_manager=task_manager),
            CompactTool(),
        ]
    )


def build_tool_runner(
    ctx: AppContext,
    registry: ToolRegistry,
    on_tool_use: Callable[[str, JsonObject], None] | None = None,
) -> ToolRunner:
    """组合 ``ToolRunner`` 与权限 / 钩子，让 PreToolUse → permission → exec → PostToolUse 流水线生效。"""
    return ToolRunner(
        registry=registry,
        on_tool_use=on_tool_use,
        permission=ctx.permission,
        hooks=ctx.hooks,
    )
