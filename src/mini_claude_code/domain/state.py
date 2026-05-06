from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def generate_session_id() -> str:
    """生成一次任务的会话 ID。"""
    return str(uuid.uuid4())


@dataclass
class LoopState:
    """Agent 循环的运行状态。

    - ``messages``: 历史消息（包含 tool_use / tool_result 等内部块）
    - ``turn_count``: 当前已经走过多少轮
    - ``transition_reason``: 上一轮为什么继续 / 终止
    - ``session_id``: 当前任务的会话 ID，用于 usage 统计分桶
    """

    messages: list = field(default_factory=list)
    turn_count: int = 1
    transition_reason: str | None = None
    session_id: str | None = None
