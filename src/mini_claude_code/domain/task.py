from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, get_args

TaskStatus = Literal["pending", "in_progress", "completed", "deleted"]
TASK_STATUSES: tuple[TaskStatus, ...] = get_args(TaskStatus)


@dataclass(slots=True)
class Task:
    """任务"""

    id: int  # 任务 id
    subject: str  # 任务主题
    description: str  # 任务描述
    status: TaskStatus
    blocked_by: list[int]  # 被哪些任务阻塞
    blocks: list[int]  # 阻塞了哪些任务
    owner: str  # 任务所有者

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data.get("id", 0),
            subject=data.get("subject", ""),
            description=data.get("description", ""),
            status=data.get("status", "pending"),
            blocked_by=data.get("blocked_by", []),
            blocks=data.get("blocks", []),
            owner=data.get("owner", ""),
        )

    def is_ready(self) -> bool:
        return self.status == "pending" and not self.blocked_by

    def update(
        self,
        status: TaskStatus,
        add_blocked_by: list[int] = None,
        remove_blocked_by: list[int] = None,
        add_blocks: list[int] = None,
        remove_blocks: list[int] = None,
    ) -> None:
        if status:
            if status not in TASK_STATUSES:
                raise ValueError(f"Invalid status: {status}")
            self.status = status

        if add_blocked_by:
            self.blocked_by = list(set(self.blocked_by + add_blocked_by))
        if remove_blocked_by:
            self.blocked_by = [x for x in self.blocked_by if x not in remove_blocked_by]

        if add_blocks:
            self.blocks = list(set(self.blocks + add_blocks))
        if remove_blocks:
            self.blocks = [x for x in self.blocks if x not in remove_blocks]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "blocked_by": list(self.blocked_by),
            "blocks": list(self.blocks),
            "owner": self.owner,
        }
