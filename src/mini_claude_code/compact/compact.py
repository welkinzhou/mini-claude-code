from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mini_claude_code.domain.workspace import WorkspacePaths
from mini_claude_code.providers.llm.spec import LLMCaller


KEEP_RECENT_TOOL_RESULTS = 3
PRESERVE_RESULT_TOOLS = {"read_file"}

# 持久化大型输出的阈值与预览长度
PERSIST_THRESHOLD = 30000
PREVIEW_CHARS = 2000


@dataclass
class CompactState:
    """压缩相关的会话级状态。

    每个 ``agent_loop`` 调用持有一份；在 CLI 长会话中可被多个调用共享，
    以维持 ``recent_files`` 等跨轮信息。

    ``pending_manual`` / ``pending_focus``：LLM 显式调用 compact 工具时，
    工具将这两个字段置为有效值，由 ``after_turn`` 订阅者在本轮结束后执行压缩。
    """

    has_compacted: bool = False
    last_summary: str = ""
    recent_files: list[str] = field(default_factory=list)
    pending_manual: bool = False
    pending_focus: str | None = None

    def reset(self) -> None:
        self.has_compacted = False
        self.last_summary = ""
        self.recent_files = []
        self.pending_manual = False
        self.pending_focus = None


def estimate_context_size(messages: list) -> int:
    """估计消息大小（粗略：4 字符 ≈ 1 token）。"""
    return len(str(messages)) // 4


def track_recent_file(state: CompactState, path: str) -> None:
    """跟踪最近使用的文件，避免重复使用，最多保留 5 个。"""
    if path in state.recent_files:
        state.recent_files.remove(path)
    state.recent_files.append(path)
    if len(state.recent_files) > 5:
        state.recent_files[:] = state.recent_files[-5:]


def collect_tool_result_blocks(messages: list) -> list[tuple[int, int, dict]]:
    """收集所有 ``tool_result`` 块及其位置。"""
    blocks = []
    for message_index, message in enumerate(messages):
        content = message.get("content")
        if message.get("role") != "user" or not isinstance(content, list):
            continue
        for block_index, block in enumerate(content):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                blocks.append((message_index, block_index, block))
    return blocks


def micro_compact(messages: list) -> list:
    """微型压缩：把更早的 ``tool_result`` 替换成占位符，保留最近若干条。"""
    tool_results = collect_tool_result_blocks(messages)
    if len(tool_results) <= KEEP_RECENT_TOOL_RESULTS:
        return messages

    for _, _, block in tool_results[:-KEEP_RECENT_TOOL_RESULTS]:
        content = block.get("content", "")
        if not isinstance(content, str) or len(content) <= 120:
            continue
        block["content"] = (
            "[Earlier tool result compacted. Re-run the tool if you need full detail.]"
        )
    return messages


def persist_large_output(
    tool_use_id: str,
    output: str,
    workspace: WorkspacePaths,
) -> str:
    """超大输出落盘并返回带预览的引用文本，控制对话窗口大小。"""
    if len(output) <= PERSIST_THRESHOLD:
        return output

    workspace.tool_outputs_dir.mkdir(parents=True, exist_ok=True)
    stored_path = workspace.tool_outputs_dir / f"{tool_use_id}.txt"
    if not stored_path.exists():
        stored_path.write_text(output)

    preview = output[:PREVIEW_CHARS]
    rel_path = stored_path.relative_to(workspace.work_path)
    return (
        "<persisted-output>\n"
        f"Full output saved to: {rel_path}\n"
        "Preview:\n"
        f"{preview}\n"
        "</persisted-output>"
    )


def write_transcript(messages: list, workspace: WorkspacePaths) -> Path:
    """完整 conversation 写入磁盘，返回路径。"""
    workspace.transcripts_dir.mkdir(parents=True, exist_ok=True)
    path = workspace.transcripts_dir / f"transcript_{int(time.time())}.jsonl"
    with path.open("w") as handle:
        for message in messages:
            handle.write(json.dumps(message, default=str) + "\n")
    return path


def summarize_history(
    messages: list,
    client: Any,
    *,
    llm_call: LLMCaller,
    model: str | None = None,
) -> str:
    """让 LLM 把整段对话总结成续作摘要。"""
    conversation = json.dumps(messages, default=str)[:80000]
    prompt = (
        "Summarize this coding-agent conversation so work can continue.\n"
        "Preserve:\n"
        "1. The current goal\n"
        "2. Important findings and decisions\n"
        "3. Files read or changed\n"
        "4. Remaining work\n"
        "5. User constraints and preferences\n"
        "Be compact but concrete.\n\n"
        f"{conversation}"
    )
    response = llm_call(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )
    return response.content[0].text.strip()


def compact_history(
    client: Any,
    messages: list,
    *,
    compact_state: CompactState,
    workspace: WorkspacePaths,
    llm_call: LLMCaller,
    focus: str | None = None,
    model: str | None = None,
) -> list:
    """调用 LLM 压缩 conversation，返回新的 messages 列表。"""
    transcript_path = write_transcript(messages, workspace)
    print(f"[transcript saved: {transcript_path}]")

    summary = summarize_history(
        messages=messages, client=client, llm_call=llm_call, model=model
    )
    if focus:
        summary += f"\n\nFocus to preserve next: {focus}"
    if compact_state.recent_files:
        recent_lines = "\n".join(f"- {path}" for path in compact_state.recent_files)
        summary += f"\n\nRecent files to reopen if needed:\n{recent_lines}"

    compact_state.has_compacted = True
    compact_state.last_summary = summary

    return [
        {
            "role": "user",
            "content": (
                "This conversation was compacted so the agent can continue working.\n\n"
                f"{summary}"
            ),
        }
    ]
