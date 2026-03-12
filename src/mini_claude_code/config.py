"""Configuration module.

This module is the **only** place that loads environment variables from `.env`.
All other modules should read configuration via :class:`Config`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment variables once, early, and consistently.
load_dotenv(override=True)

# https://docs.python.org/zh-cn/3/library/dataclasses.html
# dataclass 会自动生成 __init__ 方法、__repr__ 方法、__eq__ 方法等
# frozen=True 表示类是不可变的
# slots=True 不能动态添加属性
@dataclass(frozen=True, slots=True)
class Config:
    api_key: str | None
    api_base: str | None
    model_id: str | None

    # 类方法，用于从环境变量中创建 Config 实例
    # cls 表示类本身，self 表示实例
    # 返回 config 实例，比 init 灵活
    @classmethod
    def from_env(cls) -> "Config":
        api_base = os.getenv("ANTHROPIC_BASE_URL")
        if api_base:
            # When using a custom base URL, Anthropic SDK supports env-based auth tokens.
            # We intentionally clear this to keep auth behavior explicit via API key.
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            api_base=api_base,
            model_id=os.getenv("MODEL_ID"),
        )

    def require_api_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("Missing required env var: ANTHROPIC_API_KEY")
        return self.api_key

    def require_model_id(self) -> str:
        if not self.model_id:
            raise RuntimeError("Missing required env var: MODEL_ID")
        return self.model_id