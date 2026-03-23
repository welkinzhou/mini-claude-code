from __future__ import annotations

import json
import traceback as tb
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .serializers import to_jsonable
from .types import LogRecord


class LLMCallLogger:
    """
    JSONL logger for each client.messages.create call.
    Hardcoded file path by design.
    """

    def __init__(self) -> None:
        self.log_path = Path("logs/llm_calls.jsonl")
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
        return datetime.now(UTC).isoformat()
