from __future__ import annotations

from typing import Any, Protocol

JsonObject = dict[str, Any]


class LLMCaller(Protocol):
    """Provider-agnostic LLM call interface.

    Keep this small so core/runtime/compact can depend on it without
    importing concrete providers (Anthropic / OpenAI / ...).
    """

    def __call__(
        self,
        *,
        client: Any,
        model: str | None = None,
        system: str | None = None,
        messages: list | None = None,
        tools: list[JsonObject] | None = None,
        max_tokens: int | None = None,
    ) -> Any: ...
