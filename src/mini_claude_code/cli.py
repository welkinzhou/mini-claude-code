from __future__ import annotations

from typing import Any

from mini_claude_code.config import Config
from mini_claude_code.core.agent import AgentLoopConfig, agent_loop
from mini_claude_code.llm.anthropic_client import create_anthropic_client
from mini_claude_code.tools.bash import BashTool
from mini_claude_code.tools.read_file import ReadFileTool
from mini_claude_code.tools.write_file import WriteFileTool
from mini_claude_code.tools.edit_file import EditFileTool
from mini_claude_code.tools.registry import ToolRegistry
from mini_claude_code.tools.runner import ToolRunner
from mini_claude_code.tools.sub_agent import SubAgentTool
from mini_claude_code.tools.todo import TodoTool
from mini_claude_code.tools.path_safety import get_workdir


# 系统提示词
def _default_system_prompt() -> str:
    return f"""You are a coding agent at {get_workdir()}. Use the task tool to delegate exploration or subtasks."""


SUBAGENT_SYSTEM = f"You are a coding subagent at {get_workdir()}. Complete the given task, then summarize your findings."


def main() -> None:
    # 加载环境变量
    config = Config.from_env()
    # 创建 Anthropic 客户端
    client = create_anthropic_client(config)
    # 获取模型 ID
    model_id = config.require_model_id()
    # 创建 Agent 循环配置
    loop_config = AgentLoopConfig(
        model=model_id, system=_default_system_prompt(), max_tokens=8000
    )

    # 子 agent 受限工具集
    sub_registry = ToolRegistry.from_tools(
        [ReadFileTool(), BashTool(), WriteFileTool(), EditFileTool()]
    )
    sub_loop_config = AgentLoopConfig(
        model=model_id, system=SUBAGENT_SYSTEM, max_tokens=8000
    )
    sub_agent_tool = SubAgentTool(
        client=client, config=sub_loop_config, registry=sub_registry
    )

    # 主 agent 工具注册表（包含 sub_agent）
    registry = ToolRegistry.from_tools(
        [
            BashTool(),
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            TodoTool(),
            sub_agent_tool,
        ]
    )

    # 定义工具使用回调函数
    def on_tool_use(tool_name: str, tool_input: dict[str, Any]) -> None:
        if tool_name == "bash" and isinstance(tool_input.get("command"), str):
            print(f"\033[33m$ {tool_input['command']}\033[0m")

    tool_runner = ToolRunner(registry=registry, on_tool_use=on_tool_use)

    # 历史消息列表
    history: list[dict[str, Any]] = []
    # 循环直到用户退出
    while True:
        try:
            # 获取用户输入
            query = input("\033[36mmini >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        # 如果用户输入退出命令，则退出循环
        if query.strip().lower() in ("q", "quit", "exit", ""):
            break
        # 将用户输入添加到历史消息列表
        history.append({"role": "user", "content": query})
        # 执行 Agent 循环
        _, usage = agent_loop(
            messages=history,
            client=client,
            tools=registry.tool_specs(),
            tool_runner=tool_runner,
            config=loop_config,
        )

        # 获取最后一个消息的响应内容
        response_content = history[-1]["content"]
        # 如果响应内容是列表，则遍历列表
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    # 任务完成后反馈
                    print(block.text)

        # 打印本次任务 token 用量
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_create = usage.get("cache_creation_input_tokens", 0)
        parts = [
            f"in={usage.get('input_tokens', 0)}",
            f"out={usage.get('output_tokens', 0)}",
        ]
        if cache_read:
            parts.append(f"cache_read={cache_read}")
        if cache_create:
            parts.append(f"cache_create={cache_create}")
        print(f"\033[90m[tokens] {'  '.join(parts)}\033[0m")
        print()
