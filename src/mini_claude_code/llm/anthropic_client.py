from __future__ import annotations

from anthropic import Anthropic

from mini_claude_code.config import Config


def create_anthropic_client(config: Config) -> Anthropic:
    """Create an Anthropic client from config.

    The Anthropic SDK will read auth from env; config is responsible for env loading.
    """

    # Keep behavior compatible with the previous demo:
    # - base_url optional
    # - auth via env var (ANTHROPIC_API_KEY) already loaded by config
    if config.api_base:
        return Anthropic(base_url=config.api_base, api_key=config.api_key)
    return Anthropic()

