"""唯一允许做装配 / 副作用的层。

凡是涉及读环境、读磁盘、构造长寿命单例的工作都集中在这里完成；
其它模块只接收已经准备好的 ``AppContext``，不再各自 ``Path.cwd()``。
"""

from __future__ import annotations

from typing import Callable

from dotenv import load_dotenv

from mini_claude_code.compact.compact import CompactState
from mini_claude_code.domain.usage import UsageCalculator
from mini_claude_code.infra.llm_logger import LLMCallLogger
from mini_claude_code.providers.llm.anthropic import create_anthropic_client
from mini_claude_code.providers.skills import SkillLoader
from mini_claude_code.runtime.hooks import HookManager
from mini_claude_code.runtime.loop import AgentLoopConfig
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

from .config import AppConfig
from .context import AppContext
from .workspace import WorkspacePaths


def _main_system_prompt(workspace: WorkspacePaths, skill_loader: SkillLoader) -> str:
    return (
        f"你是一个工作在 {workspace.work_path} 目录下的代码助手。\n"
        "使用工具解决问题，涉及相关方向的知识，使用 load_skill 工具添加专业 skill。\n"
        "skill列表:\n"
        f"{skill_loader.describe_available()}"
    )


def _subagent_system_prompt(workspace: WorkspacePaths) -> str:
    return (
        f"你是一个工作在 {workspace.work_path} 目录下的子 Agent。"
        "完成给定的任务，然后总结你的发现。"
    )


def build_app_context(mode: str = "default", *, max_tokens: int = 8000) -> AppContext:
    """加载 .env、构造所有会话级依赖，返回一个完全装配好的 ``AppContext``。

    这是整个项目里唯一允许产生 import-time 副作用的地方。
    """
    load_dotenv(override=True)

    config = AppConfig.from_env()
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

    main_loop_config = AgentLoopConfig(
        model=model_id,
        system=_main_system_prompt(workspace, skill_loader),
        max_tokens=max_tokens,
    )
    sub_loop_config = AgentLoopConfig(
        model=model_id,
        system=_subagent_system_prompt(workspace),
        max_tokens=max_tokens,
    )

    return AppContext(
        config=config,
        workspace=workspace,
        client=client,
        llm_logger=llm_logger,
        skill_loader=skill_loader,
        permission=permission,
        hooks=hooks,
        usage=usage,
        compact_state=compact_state,
        main_loop_config=main_loop_config,
        sub_loop_config=sub_loop_config,
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
            CompactTool(client=ctx.client, model_id=ctx.config.require_model_id()),
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
