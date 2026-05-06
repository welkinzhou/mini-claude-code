from __future__ import annotations

import json
import traceback as tb
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import uuid4

from .serializers import to_jsonable


EventType = Literal["llm_request", "llm_response", "llm_error"]


class LogRecord(TypedDict, total=False):
    ts: str
    event: EventType
    call_id: str

    # request fields
    model: str
    system: str
    max_tokens: int
    messages: Any
    tools: Any

    # response fields
    response: Any

    # error fields
    error_type: str
    error: str
    traceback: str


class LLMCallLogger:
    """JSONL logger for each ``client.messages.create`` call.

    日志路径通过构造函数注入。默认值仅作为兼容回退，新代码请显式传入。
    """

    DEFAULT_LOG_PATH = Path("logs/llm_calls.jsonl")

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or self.DEFAULT_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def new_call_id(self) -> str:
        return str(uuid4())

    def log_request(
        self,
        *,
        call_id: str,
        model: str,
        system: str,
        messages: Any,
        tools: Any,
        max_tokens: int,
    ) -> None:
        record: LogRecord = {
            "ts": self._now(),
            "event": "llm_request",
            "call_id": call_id,
            "model": model,
            "system": system,
            "max_tokens": max_tokens,
            "messages": to_jsonable(messages),
            "tools": to_jsonable(tools),
        }
        self._write(record)

    def log_response(self, *, call_id: str, response: Any) -> None:
        record: LogRecord = {
            "ts": self._now(),
            "event": "llm_response",
            "call_id": call_id,
            "response": to_jsonable(response),
        }
        self._write(record)

    def log_error(self, *, call_id: str, error: Exception) -> None:
        record: LogRecord = {
            "ts": self._now(),
            "event": "llm_error",
            "call_id": call_id,
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": tb.format_exc(),
        }
        self._write(record)

    def _write(self, record: LogRecord) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).strftime("%Y:%m:%d %H:%M:%S")
