from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppConfig:
    """应用级配置。

    与原来的 ``Config`` 相比有两点变化：

    1. 模块本身不再调用 ``load_dotenv``。环境变量加载由 ``app.bootstrap``
       在程序启动时一次性完成。
    2. 不再生成模块级单例，所有需要配置的对象都从 ``AppContext`` 拿到这份实例。
    """

    api_key: str | None
    api_base: str | None
    model_id: str | None

    @classmethod
    def from_env(cls) -> "AppConfig":
        api_base = os.getenv("ANTHROPIC_BASE_URL")
        if api_base:
            # 自定义 base_url 时显式清空 SDK 自动读取的 token，避免双 auth 干扰。
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
