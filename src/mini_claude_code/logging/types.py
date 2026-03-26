from __future__ import annotations

from typing import Any, Literal, TypedDict

EventType = Literal["llm_request", "llm_response", "llm_error"]


class TokenUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


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
