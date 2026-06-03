from __future__ import annotations
from pathlib import Path

import re

import yaml


"""
解析 Markdown 文件，返回 metadata 和 body。

metadata 格式为 yaml 格式，body 格式为 markdown 格式。

例如:
---
name: 记忆名称
description: 记忆描述
type: 记忆类型
---

记忆内容


使用 yaml 解析 metadata
"""


def parse_md_file(file_path: Path) -> dict:
    """解析 Markdown 文件，返回 metadata 和 body。"""
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    # 没有元数据
    if not match:
        return {}, content.strip()
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid metadata: {metadata}")
    body = match.group(2).strip()
    if not isinstance(body, str):
        raise ValueError(f"Invalid body: {body}")
    return metadata, body
