from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """工作区根目录及其下所有约定路径的集中描述。

    把项目里散落的路径常量（``.tasks``、``.transcripts``、``.hooks.json`` 等）
    全部收敛到这里，避免每个模块各自调用 ``Path.cwd()``。

    本身只是值对象（Value Object），不做任何 IO；真正的目录访问由调用方触发
    （例如 ``mkdir`` / ``read_text``），因此可以安全地放在 domain 层。
    """

    work_path: Path

    @classmethod
    def from_cwd(cls) -> "WorkspacePaths":
        return cls(work_path=Path.cwd())

    # -- 业务子目录 --
    @property
    def skills_dir(self) -> Path:
        return self.work_path / "skills"

    @property
    def tasks_dir(self) -> Path:
        return self.work_path / ".tasks"

    @property
    def transcripts_dir(self) -> Path:
        return self.work_path / ".transcripts"

    @property
    def tool_outputs_dir(self) -> Path:
        return self.work_path / ".task_outputs" / "tool-results"

    @property
    def logs_dir(self) -> Path:
        return self.work_path / "logs"

    # -- 信任 / 钩子 --
    @property
    def trust_marker(self) -> Path:
        return self.work_path / ".claude" / ".claude_trusted"

    @property
    def hooks_config(self) -> Path:
        return self.work_path / ".hooks.json"

    @property
    def llm_call_log(self) -> Path:
        return self.logs_dir / "llm_calls.jsonl"

    @property
    def memories_dir(self) -> Path:
        return self.work_path / ".memory"
