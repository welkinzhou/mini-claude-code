from dataclasses import dataclass

import json
from pathlib import Path

from .base import JsonObject, ToolSpec
from .runner import ToolRunner


class TaskManager:
    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(exist_ok=True)
        self._next_id = self._max_id() + 1  # 下一个任务ID

    def _max_id(self) -> int:
        # 获取存储的任务文件中最大的任务ID
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        # 加载任务
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())

    def _save(self, task: dict):
        # 保存任务
        path = self.dir / f"task_{task['id']}.json"
        path.write_text(json.dumps(task, indent=2, ensure_ascii=False))

    def create(self, subject: str, description: str = "") -> str:
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "blockedBy": [],  # 依赖的任务ID列表
            "owner": "",  # 任务所有者
        }
        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2, ensure_ascii=False)

    def get(self, task_id: int) -> str:
        return json.dumps(self._load(task_id), indent=2, ensure_ascii=False)

    def update(
        self,
        task_id: int,
        status: str = None,
        add_blocked_by: list = None,
        remove_blocked_by: list = None,
    ) -> str:
        task = self._load(task_id)
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                # 完成任务后，清除依赖
                self._clear_dependency(task_id)
        # 修改依赖关系
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))
        if remove_blocked_by:
            task["blockedBy"] = [
                x for x in task["blockedBy"] if x not in remove_blocked_by
            ]
        self._save(task)
        return json.dumps(task, indent=2, ensure_ascii=False)

    def _clear_dependency(self, completed_id: int):
        """Remove completed_id from all other tasks' blockedBy lists."""
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self._save(task)

    def list_all(self) -> str:
        tasks = []
        files = sorted(
            self.dir.glob("task_*.json"), key=lambda f: int(f.stem.split("_")[1])
        )
        for f in files:
            tasks.append(json.loads(f.read_text()))
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}.get(
                t["status"], "[?]"
            )
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class TaskTool:
    task_manager: TaskManager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="task",
            description="Manage tasks and their dependencies.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "enum": ["create", "get", "update", "list"],
                        "description": "The action to perform",
                    },
                },
                "required": ["action"],
                "allOf": [
                    {
                        "if": {
                            "properties": {
                                "action": {"const": "create"},
                            },
                        },
                        "then": {
                            "properties": {
                                "subject": {
                                    "type": "string",
                                    "description": "The subject of the task",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "The description of the task",
                                },
                            },
                            "required": ["subject"],
                        },
                    },
                    {
                        "if": {
                            "properties": {
                                "action": {"const": "get"},
                            },
                        },
                        "then": {
                            "properties": {
                                "task_id": {
                                    "type": "integer",
                                    "description": "The ID of the task",
                                },
                            },
                            "required": ["task_id"],
                        },
                    },
                    {
                        "if": {
                            "properties": {
                                "action": {"const": "update"},
                            },
                        },
                        "then": {
                            "properties": {
                                "task_id": {
                                    "type": "integer",
                                    "description": "The ID of the task",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "The status of the task",
                                },
                                "add_blocked_by": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "The IDs of the tasks to add as dependencies",
                                },
                                "remove_blocked_by": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "The IDs of the tasks to remove as dependencies",
                                },
                            },
                            "required": ["task_id", "status"],
                        },
                    },
                ],
            },
            input_examples=[
                {
                    "action": "create",
                    "subject": "Task 1",
                    "description": "Description 1",
                },
                {
                    "action": "get",
                    "task_id": 1,
                },
                {
                    "action": "update",
                    "task_id": 1,
                    "status": "completed",
                },
                {
                    "action": "update",
                    "task_id": 1,
                    "status": "pending",
                    "add_blocked_by": [2],
                    "remove_blocked_by": [3],
                },
                {
                    "action": "list",
                },
            ],
        )

    def run(self, input: JsonObject, _: ToolRunner) -> str:
        action = input.get("action")
        if action == "create":
            return self.create(input.get("subject"), input.get("description"))
        elif action == "get":
            return self.get(input.get("task_id"))
        elif action == "update":
            add_blocked_by = input.get("add_blocked_by", [])
            remove_blocked_by = input.get("remove_blocked_by", [])
            return self.update(
                input.get("task_id"),
                input.get("status"),
                add_blocked_by,
                remove_blocked_by,
            )
        else:
            return self.list_all()

    def create(self, subject: str, description: str = "") -> str:
        return self.task_manager.create(subject, description)

    def get(self, task_id: int) -> str:
        return self.task_manager.get(task_id)

    def update(
        self,
        task_id: int,
        status: str = None,
        add_blocked_by: list = None,
        remove_blocked_by: list = None,
    ) -> str:
        return self.task_manager.update(
            task_id, status, add_blocked_by, remove_blocked_by
        )

    def list_all(self) -> str:
        return self.task_manager.list_all()
