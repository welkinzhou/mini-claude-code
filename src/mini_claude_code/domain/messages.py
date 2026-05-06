from __future__ import annotations


# messages 清洗，和模型对话，只需要用到 API 规定的数据
# messages 中还会有异常中断等应用内部消息
# API 协议有三条硬性约束:
# - 每个 tool_use 块必须有匹配的 tool_result (通过 tool_use_id 关联)
# - user / assistant 消息必须严格交替 (不能连续两条同角色)
# - 只接受协议定义的字段 (内部元数据会导致 400 错误)
def normalize_messages(messages: list) -> list:
    """将内部消息列表规范化为 API 可接受的格式。"""
    normalized = []

    for msg in messages:
        # Step 1: 剥离内部字段
        clean = {"role": msg["role"]}
        if isinstance(msg.get("content"), str):
            clean["content"] = msg["content"]
        elif isinstance(msg.get("content"), list):
            clean["content"] = [
                {
                    k: v
                    for k, v in block.items()
                    if k not in ("_internal", "_source", "_timestamp")
                }
                for block in msg["content"]
            ]
        normalized.append(clean)

    # Step 2: tool_result 配对补齐
    existing_results = set()
    for msg in normalized:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if block.get("type") == "tool_result":
                    existing_results.add(block.get("tool_use_id"))

    for msg in normalized:
        if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if (
                    block.get("type") == "tool_use"
                    and block.get("id") not in existing_results
                ):
                    normalized.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block["id"],
                                    "content": "(cancelled)",
                                }
                            ],
                        }
                    )

    # Step 3: 合并连续同角色消息
    merged = [normalized[0]] if normalized else []
    for msg in normalized[1:]:
        if msg["role"] == merged[-1]["role"]:
            prev = merged[-1]
            prev_content = (
                prev["content"]
                if isinstance(prev["content"], list)
                else [{"type": "text", "text": prev["content"]}]
            )
            curr_content = (
                msg["content"]
                if isinstance(msg["content"], list)
                else [{"type": "text", "text": msg["content"]}]
            )
            prev["content"] = prev_content + curr_content
        else:
            merged.append(msg)

    return merged
