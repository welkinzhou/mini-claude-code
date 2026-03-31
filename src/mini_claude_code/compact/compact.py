import json
import time
from mini_claude_code.tools.path_safety import get_workdir

from anthropic import Anthropic

TRANSCRIPT_DIR = get_workdir() / ".transcripts"
KEEP_RECENT = 3
PRESERVE_RESULT_TOOLS = {"read_file"}


def micro_compact(messages: list) -> list:
    """
    Replace old tool results with placeholders.
    """
    tool_results = []
    # 遍历 message 列表，找到所有的 tool_result 条目
    for msg_idx, msg in enumerate(messages):
        # 只有用户会返回 tool_result
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            # 遍历用户的消息 content，找到所有的 tool_result 条目
            for part_idx, part in enumerate(msg["content"]):
                # 如果 part 是 dict 类型，并且 type 是 tool_result，则将 part 添加到 tool_results 列表中
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    # msg_idx: 消息的索引
                    # part_idx: 消息内容的索引
                    # part: tool_result 条目
                    tool_results.append((msg_idx, part_idx, part))
    # 如果 tool_results 列表的长度小于等于 KEEP_RECENT，无需压缩
    if len(tool_results) <= KEEP_RECENT:
        return messages
    # 找出每个 tool_result 对应的 tool_name
    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name
    # 保留最近三条 tool_result，其他的替换为 placeholder
    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        # 如果 content 不是字符串，或者长度小于 100，则跳过
        if not isinstance(result.get("content"), str) or len(result["content"]) <= 100:
            continue
        tool_id = result.get("tool_use_id", "")
        tool_name = tool_name_map.get(tool_id, "unknown")
        # 有些操作需要保留信息，例如 read_file
        # 文件中内容影响后续推理结果，不能被替换
        if tool_name in PRESERVE_RESULT_TOOLS:
            continue
        # 不影响后续推理的 tool_result，替换为 placeholder
        result["content"] = f"[Previous: used {tool_name}]"
    return messages


def auto_compact(client: Anthropic, model_id: str, messages: list) -> list:
    # Save full transcript to disk
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    print(f"[transcript saved: {transcript_path}]")
    # Ask LLM to summarize
    conversation_text = json.dumps(messages, default=str)[-80000:]
    response = client.messages.create(
        model=model_id,
        messages=[
            {
                "role": "user",
                "content": "Summarize this conversation for continuity. Include: "
                "1) What was accomplished, 2) Current state, 3) Key decisions made. "
                "Be concise but preserve critical details.\n\n" + conversation_text,
            }
        ],
        max_tokens=2000,
    )
    summary = response.content[0].text
    # Replace all messages with compressed summary
    return [
        {
            "role": "user",
            "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}",
        },
    ]
