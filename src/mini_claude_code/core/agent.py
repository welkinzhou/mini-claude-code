# 延迟类型注解的求值‌ 3.10 后默认行为，这里为了兼容
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mini_claude_code.tools.runner import ToolRunner

from mini_claude_code.logging.llm_logger import LLMCallLogger
from mini_claude_code.logging.types import TokenUsage

from mini_claude_code.compact.compact import micro_compact, auto_compact

JsonObject = dict[str, Any]

THRESHOLD = 50000


@dataclass(frozen=True, slots=True)
class AgentLoopConfig:
    model: str
    system: str
    max_tokens: int = 8000


def estimate_tokens(messages: list) -> int:
    """Rough token count: ~4 chars per token."""
    return len(str(messages)) // 4


llm_call_logger = LLMCallLogger()

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
) -> tuple[Any, TokenUsage]:
    """Run the core tool-use loop until the model stops calling tools."""
    call_id = llm_call_logger.new_call_id()
    total_usage: TokenUsage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    while True:
        # 简单压缩消息
        messages = micro_compact(messages)
        # 如果消息长度超过阈值，则使用 llm 总结压缩
        if estimate_tokens(messages) > THRESHOLD:
            print("[auto_compact triggered]")
            messages[:] = auto_compact(client, config.model, messages)
        try:
            # 写入请求参数
            llm_call_logger.log_request(
                call_id=call_id,
                model=config.model,
                system=config.system,
                messages=messages,
                tools=tools,
                max_tokens=config.max_tokens,
            )
            # 请求大模型，返回响应
            response = client.messages.create(
                model=config.model,
                system=config.system,
                messages=messages,
                tools=tools,
                max_tokens=config.max_tokens,
            )
            # 写入响应参数
            llm_call_logger.log_response(
                call_id=call_id,
                response=response,
            )
        # except KeyboardInterrupt:
        #     raise
        except Exception as e:
            # 写入错误参数
            llm_call_logger.log_error(
                call_id=call_id,
                error=e,
            )
            # 尽量拿到“message”
            err_msg = getattr(e, "message", None) or str(e)
            print(f"\033[31mllm error: {err_msg}\033[0m")  # 红色错误输出
            # 不让程序结束：直接结束本次 agent_loop，让 cli 回到下一轮输入
            return {"error": err_msg}, total_usage

        # 累计本轮 token 用量
        u = response.usage
        total_usage["input_tokens"] += getattr(u, "input_tokens", 0)
        total_usage["output_tokens"] += getattr(u, "output_tokens", 0)
        total_usage["cache_creation_input_tokens"] += getattr(
            u, "cache_creation_input_tokens", 0
        )
        total_usage["cache_read_input_tokens"] += getattr(
            u, "cache_read_input_tokens", 0
        )

        # 将响应添加到消息列表
        messages.append({"role": "assistant", "content": response.content})

        # 如果模型没有调用工具，则返回响应
        if response.stop_reason != "tool_use":
            return response, total_usage
        # 执行工具，收集结果
        results = tool_runner.run_from_response_content(response.content)

        # 将结果添加到消息列表
        messages.append({"role": "user", "content": results})

        if tool_runner.pending_compact:
            tool_runner.pending_compact = False
            print("[manual compact]")
            messages[:] = auto_compact(client, config.model, messages)
