"""纯业务对象层。

要求：
- 没有任何 import-time 副作用；
- 不依赖 ``app/runtime/tools/providers/infra``，可被任何上层模块自由 import。
"""

from .config import AppConfig
from .state import LoopState, generate_session_id
from .messages import normalize_messages
from .usage import TokenUsage, UsageCalculator
from .workspace import WorkspacePaths
from .memory import Memory, MEMORY_TYPES, MAX_INDEX_LINES, MEMORY_GUIDANCE

__all__ = [
    "AppConfig",
    "LoopState",
    "generate_session_id",
    "normalize_messages",
    "TokenUsage",
    "UsageCalculator",
    "WorkspacePaths",
    "Memory",
    "MEMORY_TYPES",
    "MAX_INDEX_LINES",
    "MEMORY_GUIDANCE",
]
