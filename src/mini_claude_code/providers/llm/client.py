from __future__ import annotations

from typing import Any

JsonObject = dict[str, Any]


def call_llm(
    *,
    client: Any,
    model: str | None = None,
    system: str | None = None,
    messages: list | None = None,
    tools: list[JsonObject] | None = None,
    max_tokens: int | None = None,
) -> Any:
    """Call LLM with normalized messages and tools."""
    return client.messages.create(
        model=model,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
    )
