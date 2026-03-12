# 延迟类型注解的求值‌ 3.10 后默认行为，这里为了兼容
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from mini_claude_code.tools.runner import ToolRunner


JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentLoopConfig:
    model: str
    system: str
    max_tokens: int = 8000

"""
Agent 循环，用于运行核心工具使用循环，直到模型停止调用工具

Anthropic Tool call response 结构如下:
{
  "id": "msg_abc",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "我需要获取订单信息。"
    },
    {
      "type": "tool_use",
      "id": "toolu_123",
      "name": "get_customer_orders",
      "input": {}
    }
  ],
  "stop_reason": "tool_use",
  "usage": { ... }
}

"""


def agent_loop(
    *,
    messages: list[JsonObject],
    client: Any,
    tools: list[JsonObject],
    tool_runner: ToolRunner,
    config: AgentLoopConfig,
) -> Any:
    """Run the core tool-use loop until the model stops calling tools."""

    while True:
        # 请求大模型，返回响应
        response = client.messages.create(
            model=config.model,
            system=config.system,
            messages=messages,
            tools=tools,
            max_tokens=config.max_tokens,
        )

        # 将响应添加到消息列表
        messages.append({"role": "assistant", "content": response.content})

        # 如果模型没有调用工具，则返回响应
        if response.stop_reason != "tool_use":
            return response
        # 执行工具，收集结果
        results = tool_runner.run_from_response_content(response.content)
        # 将结果添加到消息列表
        messages.append({"role": "user", "content": results})

