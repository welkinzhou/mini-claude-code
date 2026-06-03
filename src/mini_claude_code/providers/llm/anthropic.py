from __future__ import annotations

from anthropic import Anthropic

from mini_claude_code.domain.config import AppConfig


def create_anthropic_client(config: AppConfig) -> Anthropic:
    """Create an Anthropic client from ``AppConfig``.

    The Anthropic SDK reads auth from env; ``AppConfig`` is responsible for
    sourcing env values. When ``api_base`` is set we pass it explicitly.
    """
    if config.api_base:
        return Anthropic(base_url=config.api_base, api_key=config.api_key)
    return Anthropic()
