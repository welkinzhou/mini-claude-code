# 延迟类型注解的求值‌ 3.10 后默认行为，这里为了兼容
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mini_claude_code.tools.runner import ToolRunner


from mini_claude_code.logging.llm_logger import LLMCallLogger

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


def used_todo(response_content: list[Any]) -> bool:
    for block in response_content:
        if (
            getattr(block, "type", None) == "tool_use"
            and getattr(block, "name", None) == "todo"
        ):
            return True
    return False


llm_call_logger = LLMCallLogger()


def agent_loop(
    *,
    messages: list[JsonObject],
    client: Any,
    tools: list[JsonObject],
    tool_runner: ToolRunner,
    config: AgentLoopConfig,
) -> Any:
    """Run the core tool-use loop until the model stops calling tools."""
    rounds_since_todo = 0
    call_id = llm_call_logger.new_call_id()
    while True:
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
            return {"error": err_msg}

        # 将响应添加到消息列表
        messages.append({"role": "assistant", "content": response.content})

        # 如果模型没有调用工具，则返回响应
        if response.stop_reason != "tool_use":
            return response
        # 执行工具，收集结果
        results = tool_runner.run_from_response_content(response.content)
        used_todo_flag = used_todo(response.content)

        if used_todo_flag:
            rounds_since_todo = 0
        else:
            rounds_since_todo += 1

        if rounds_since_todo >= 3:
            # 提醒信息放入尾部，tool_use 后必须立刻返回 tool_result
            # 测试是否是 messages 顺序导致
            results.append(
                {"type": "text", "text": "<reminder>Update your todos.</reminder>"}
            )
        # 将结果添加到消息列表
        messages.append({"role": "user", "content": results})
