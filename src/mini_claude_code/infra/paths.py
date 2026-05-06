from __future__ import annotations

from pathlib import Path


def safe_path(path: str, workspace: Path | None = None) -> Path:
    """把相对路径解析到 ``workspace`` 内部，越界则抛错。

    ``workspace`` 不传时退化为 ``Path.cwd()``，便于工具在拿到 ``WorkspacePaths``
    之前先用上；接入注入后，所有调用应显式传入 workspace 根目录。
    """
    root = workspace or Path.cwd()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {path}")
    return target
