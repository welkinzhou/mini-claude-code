from __future__ import annotations
import re
from pathlib import Path
from mini_claude_code.infra.md_parser import parse_md_file
from mini_claude_code.domain import (
    Memory,
    MEMORY_TYPES,
    MAX_INDEX_LINES,
)
import os


class MemoryManager:
    """
    Memory 管理器
    """

    def __init__(self, memory_dir: Path, memory_index: Path = None):
        """初始化 Memory 管理器"""
        self.memory_dir = memory_dir
        self.memory_index = memory_index or self.memory_dir / "MEMORY.md"
        self.memories: dict[str, Memory] = {}

    def load_all(self):
        """Load MEMORY.md index and all individual memory files."""
        self.memories: dict[str, Memory] = {}
        if not self.memory_dir.exists():
            return

        # 搜索 .memory 目录下的所有 .md 文件，除了 MEMORY.md 文件
        for md_file in sorted(self.memory_dir.glob("*.md")):
            if md_file.name == "MEMORY.md":
                continue
            meta, body = parse_md_file(md_file)
            if body:
                name = meta.get("name", md_file.stem)
                self.memories[name] = Memory(
                    name=name,
                    description=meta.get("description", ""),
                    type=meta.get("type", "project"),
                    content=body,
                    file=md_file.name,
                )

        count = len(self.memories)
        if count > 0:
            print(f"[Memory loaded: {count} memories from {self.memory_dir}]")

    def load_memory_prompt(self) -> str:
        """构建记忆提示，用于注入到提示词中"""
        self.load_all()
        if not self.memories:
            return ""

        sections = []
        sections.append("# Memories (persistent across sessions)")
        sections.append("")

        # 按类型分组，便于阅读
        for mem_type in MEMORY_TYPES:
            # 同类型记忆
            typed = {k: v for k, v in self.memories.items() if v["type"] == mem_type}
            if not typed:
                continue
            sections.append(f"## [{mem_type}]")
            for name, mem in typed.items():
                sections.append(f"### {name}: {mem['description']}")
                if mem["content"].strip():
                    sections.append(mem["content"].strip())
                sections.append("")

        return "\n".join(sections)

    def save_memory(
        self, name: str, description: str, mem_type: str, content: str
    ) -> str:
        """
        保存记忆到磁盘并更新索引
        """
        if mem_type not in MEMORY_TYPES:
            raise ValueError(
                f"Invalid memory type: {mem_type}. Must be one of {MEMORY_TYPES}"
            )

        # 安全的记忆名称
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        if not safe_name:
            raise ValueError(f"Invalid memory name: {name}")

        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Write individual memory file with frontmatter
        frontmatter = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"type: {mem_type}\n"
            f"---\n"
            f"{content}\n"
        )
        file_name = f"{safe_name}.md"
        file_path = self.memory_dir / file_name
        file_path.write_text(frontmatter)

        # Update in-memory store
        self.memories[name] = {
            "description": description,
            "type": mem_type,
            "content": content,
            "file": file_name,
        }

        # Rebuild MEMORY.md index
        self._rebuild_index()

        return f"Saved memory '{name}' [{mem_type}] to {file_path.relative_to(self.memory_dir)}"

    def _rebuild_index(self):
        """从当前内存状态重建 MEMORY.md，最多200行。"""
        lines = ["# Memory Index", ""]
        for name, mem in self.memories.items():
            lines.append(f"- {name}: {mem['description']} [{mem['type']}]")
            if len(lines) >= MAX_INDEX_LINES:
                lines.append(f"... (truncated at {MAX_INDEX_LINES} lines)")
                break
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_index.write_text("\n".join(lines) + "\n")


class DreamConsolidator:
    """
    自动合并、去重、修剪记忆，防止记忆堆积。

    这是一个可选的后期阶段功能。它的作用是防止记忆堆积，通过合并、去重、修剪记忆。
    """

    COOLDOWN_SECONDS = 86400  # 24 hours between consolidations
    SCAN_THROTTLE_SECONDS = 600  # 10 minutes between scan attempts
    MIN_SESSION_COUNT = 5  # need enough data to consolidate
    LOCK_STALE_SECONDS = 3600  # PID lock considered stale after 1 hour

    PHASES = [
        "定位: 扫描 MEMORY.md 索引，定位记忆结构和类别",
        "收集: 读取单独的 memory 文件获取完整内容",
        "合并: 合并相关 memory，删除过时 memory",
        "修剪: 修剪 MEMORY.md 索引，保持200行以内",
    ]

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.lock_file = self.memory_dir / ".dream_lock"
        self.enabled = True
        self.mode = "default"
        self.last_consolidation_time = 0.0
        self.last_scan_time = 0.0
        self.session_count = 0

    def should_consolidate(self) -> tuple[bool, str]:
        """
        检查7个门，所有门都必须通过。
        返回 (can_run, reason)，其中 reason 解释第一个失败的门。
        """
        import time

        now = time.time()

        # 1: 启用标志
        if not self.enabled:
            return False, "Gate 1: consolidation is disabled"

        # 2: 记忆目录存在且有记忆文件
        if not self.memory_dir.exists():
            return False, "Gate 2: memory directory does not exist"
        memory_files = list(self.memory_dir.glob("*.md"))
        # Exclude MEMORY.md itself from the count
        memory_files = [f for f in memory_files if f.name != "MEMORY.md"]
        if not memory_files:
            return False, "Gate 2: no memory files found"

        # 3: 不在计划模式下 (只在活跃模式下合并)
        if self.mode == "plan":
            return False, "Gate 3: plan mode does not allow consolidation"

        # 4: 上次合并后24小时冷却
        time_since_last = now - self.last_consolidation_time
        if time_since_last < self.COOLDOWN_SECONDS:
            remaining = int(self.COOLDOWN_SECONDS - time_since_last)
            return False, f"Gate 4: cooldown active, {remaining}s remaining"

        # 5: 上次扫描后10分钟冷却
        time_since_scan = now - self.last_scan_time
        if time_since_scan < self.SCAN_THROTTLE_SECONDS:
            remaining = int(self.SCAN_THROTTLE_SECONDS - time_since_scan)
            return False, f"Gate 5: scan throttle active, {remaining}s remaining"

        # 6: 至少需要5个会话的数据
        if self.session_count < self.MIN_SESSION_COUNT:
            return (
                False,
                f"Gate 6: only {self.session_count} sessions, need {self.MIN_SESSION_COUNT}",
            )

        # 7: 没有活动锁文件 (检查 PID 是否过期)
        if not self._acquire_lock():
            return False, "Gate 7: 文件被另一个进程锁定"

        return True, "所有7个检测都通过，可以进行合并"

    def consolidate(self) -> list[str]:
        """
        Run the 4-phase consolidation process.

        The teaching version returns phase descriptions to make the flow
        visible without requiring an extra LLM pass here.
        """
        import time

        can_run, reason = self.should_consolidate()
        if not can_run:
            print(f"[Dream] Cannot consolidate: {reason}")
            return []

        print("[Dream] Starting consolidation...")
        self.last_scan_time = time.time()

        completed_phases = []
        for i, phase in enumerate(self.PHASES, 1):
            print(f"[Dream] Phase {i}/4: {phase}")
            completed_phases.append(phase)

        self.last_consolidation_time = time.time()
        self._release_lock()
        print(
            f"[Dream] Consolidation complete: {len(completed_phases)} phases executed"
        )
        return completed_phases

    def _acquire_lock(self) -> bool:
        """
        Acquire a PID-based lock file. Returns False if locked by another
        live process. Stale locks (older than LOCK_STALE_SECONDS) are removed.
        """
        import time

        if self.lock_file.exists():
            try:
                # 获取锁定文件信息
                lock_data = self.lock_file.read_text().strip()
                pid_str, timestamp_str = lock_data.split(":", 1)
                pid = int(pid_str)
                lock_time = float(timestamp_str)

                # 检查锁定是否过期
                if (time.time() - lock_time) > self.LOCK_STALE_SECONDS:
                    print(f"[Dream] Removing stale lock from PID {pid}")
                    self.lock_file.unlink()
                else:
                    # Check if owning process is still alive
                    try:
                        os.kill(pid, 0)
                        return False  # process alive, lock is valid
                    except OSError:
                        print(f"[Dream] Removing lock from dead PID {pid}")
                        self.lock_file.unlink()
            except (ValueError, OSError):
                # Corrupted lock file, remove it
                self.lock_file.unlink(missing_ok=True)

        # Write new lock
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(f"{os.getpid()}:{time.time()}")
            return True
        except OSError:
            return False

    def _release_lock(self):
        """Release the lock file if we own it."""
        try:
            if self.lock_file.exists():
                lock_data = self.lock_file.read_text().strip()
                pid_str = lock_data.split(":")[0]
                if int(pid_str) == os.getpid():
                    self.lock_file.unlink()
        except (ValueError, OSError):
            pass
