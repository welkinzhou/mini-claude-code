from __future__ import annotations

import os
from typing import Any

from mini_claude_code.config import Config
from mini_claude_code.core.agent import AgentLoopConfig, agent_loop
from mini_claude_code.llm.anthropic_client import create_anthropic_client
from mini_claude_code.tools.bash import BashTool
from mini_claude_code.tools.registry import ToolRegistry
from mini_claude_code.tools.runner import ToolRunner

# 系统提示词
def _default_system_prompt() -> str:
    return f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."


def main() -> None:
    # 加载环境变量
    config = Config.from_env()
    # 创建 Anthropic 客户端
    client = create_anthropic_client(config)
    # 创建工具注册表
    registry = ToolRegistry.from_tools([BashTool()])
    # 定义工具使用回调函数
    def on_tool_use(tool_name: str, tool_input: dict[str, Any]) -> None:
        if tool_name == "bash" and isinstance(tool_input.get("command"), str):
            print(f"\033[33m$ {tool_input['command']}\033[0m")

    tool_runner = ToolRunner(registry=registry, on_tool_use=on_tool_use)

    # 获取模型 ID
    model_id = config.require_model_id()
    # 创建 Agent 循环配置   
    loop_config = AgentLoopConfig(model=model_id, system=_default_system_prompt(), max_tokens=8000)

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
        agent_loop(
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
                    print(block.text)
        print()

