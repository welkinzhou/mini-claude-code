from __future__ import annotations

from typing import TypedDict


class TokenUsage(TypedDict, total=False):
    """单次 LLM 请求返回的 token 用量。"""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


class UsageCalculator:
    """累计 token 用量，按 ``session_id`` 区分会话。

    外部无需做任何判断，只需在每次 LLM 请求后调用 ``add(session_id, usage)``：
    - session_id 与当前一致：累加到当前会话的合计。
    - session_id 与当前不一致：先打印上一个会话的合计、重置计数器，
      再以新的 session_id 开始累计。

    进程退出前可调用 ``flush()`` 打印最后一个会话的合计。
    """

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cache_creation_input_tokens: int = 0
        self._cache_read_input_tokens: int = 0

    def add(self, session_id: str, usage: TokenUsage) -> None:
        """累加一次请求的用量；如果会话切换，自动输出上一个会话的合计。"""
        if self._session_id is not None and self._session_id != session_id:
            self._print_and_reset()

        self._session_id = session_id
        self._input_tokens += usage.get("input_tokens", 0)
        self._output_tokens += usage.get("output_tokens", 0)
        self._cache_creation_input_tokens += usage.get("cache_creation_input_tokens", 0)
        self._cache_read_input_tokens += usage.get("cache_read_input_tokens", 0)

    def flush(self) -> None:
        """退出前手动输出当前会话的合计并清零。"""
        if self._session_id is None:
            return
        self._print_and_reset()

    def _print_and_reset(self) -> None:
        parts = [
            f"in={self._input_tokens}",
            f"out={self._output_tokens}",
        ]
        if self._cache_read_input_tokens:
            parts.append(f"cache_read={self._cache_read_input_tokens}")
        if self._cache_creation_input_tokens:
            parts.append(f"cache_create={self._cache_creation_input_tokens}")
        print(f"\033[90m[session {self._session_id} total] {'  '.join(parts)}\033[0m")

        self._session_id = None
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_creation_input_tokens = 0
        self._cache_read_input_tokens = 0
