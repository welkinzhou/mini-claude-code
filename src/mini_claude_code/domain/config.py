from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    """应用级配置值对象。

    - 字段本身（``api_key`` / ``api_base`` / ``model_id``）只是数据，没有 IO；
    - ``from_env`` 工厂方法读取环境变量，由 ``app.bootstrap`` 在装配阶段调用，
      内层模块只接收已经构造好的 ``AppConfig`` 实例。

    放在 domain 层的依据：本身是不可变值对象、不依赖任何框架，且在项目里被
    多个层（providers/llm/anthropic、app/bootstrap）共享，应避免反向依赖。
    """

    api_key: str | None
    api_base: str | None
    model_id: str | None
    agent_mode: str | None

    @classmethod
    def from_env(cls) -> "AppConfig":
        api_base = os.getenv("ANTHROPIC_BASE_URL")
        if api_base:
            # 自定义 base_url 时显式清空 SDK 自动读取的 token，避免双 auth 干扰。
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

        raw_mode = os.getenv("AGENT_MODE")
        agent_mode = raw_mode.strip().lower() if raw_mode else None

        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            api_base=api_base,
            model_id=os.getenv("MODEL_ID"),
            agent_mode=agent_mode or None,
        )

    def require_api_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("Missing required env var: ANTHROPIC_API_KEY")
        return self.api_key

    def require_model_id(self) -> str:
        if not self.model_id:
            raise RuntimeError("Missing required env var: MODEL_ID")
        return self.model_id
