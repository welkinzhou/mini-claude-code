"""
序列化模块
将日志数据转换为JSON格式
"""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Best-effort conversion to JSON-serializable Python types."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return [to_jsonable(v) for v in obj]
    # pydantic / sdk objects
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        try:
            return to_jsonable(model_dump())
        except Exception:
            pass
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return to_jsonable(to_dict())
        except Exception:
            pass
    as_dict = getattr(obj, "__dict__", None)
    if isinstance(as_dict, dict):
        return to_jsonable(as_dict)
    # final fallback
    return repr(obj)
