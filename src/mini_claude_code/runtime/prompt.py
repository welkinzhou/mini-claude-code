# prompt 管理器
# 构建系统提示词
# 系统提示词包括不变部分和动态部分
# 不变部分包括角色、目标、规则
# 动态部分包括工具、技能、记忆、claude_md、动态
# 更好利用缓存，分开管理很重要

from __future__ import annotations

from mini_claude_code.domain.workspace import WorkspacePaths
from mini_claude_code.providers.skills import SkillLoader
from mini_claude_code.runtime.memory import MemoryManager

# from mini_claude_code.runtime.tool_registry import ToolRegistry


class SystemPromptBuilder:

    def __init__(
        self,
        workspace: WorkspacePaths,
        skill_loader: SkillLoader,
        memory_manager: MemoryManager,
        # tool_registry: ToolRegistry,
    ):
        self.workspace = workspace
        self.skill_loader = skill_loader
        self.memory_manager = memory_manager
        # self.tool_registry = tool_registry # 系统工具集

    def buildSystemPrompt(
        self,
    ) -> str:
        # 主程序系统提示词
        parts = []
        parts.append(self._build_core())
        # parts.append(self._build_tools())
        parts.append(self._build_skills())
        parts.append(self._build_memory())
        # parts.append(self._build_claude_md())
        # parts.append(self._build_dynamic(workspace))
        return "\n\n".join(p for p in parts if p)

    def buildSubagentSystemPrompt(self) -> str:
        parts = []
        parts.append(f"你是一个工作在 {self.workspace.work_path} 目录下的子 Agent。")
        parts.append("完成给定的任务，总结你的发现，返回给主程序。")
        parts.append(self._build_memory())
        return "\n\n".join(p for p in parts if p)

    def _build_core(self) -> str:
        return (
            f"你是一个工作在 {self.workspace.work_path} 目录下的代码助手。\n"
            "解决问题前，先分析问题，减少废话，尽量使用工具。"
            "需要复杂任务，使用 subagent 管理任务，专注在当前步骤，及时更新进度。"
            "涉及相关方向的知识，使用 load_skill 工具添加专业 skill。\n"
        )

    # def _build_tools(self, tool_registry: ToolRegistry) -> str:
    #     return (
    #         "你拥有以下工具可用：\n"
    #         "bash: 执行 shell 命令\n"
    #         "read_file: 读取文件内容\n"
    #         "write_file: 写入文件内容\n"
    #         "edit_file: 编辑文件内容\n"
    #         "load_skill: 加载专业 skill\n"
    #         "subagent: 管理子任务\n"
    #         "task: 管理任务\n"
    #         "compact: 压缩上下文\n"
    #     )

    def _build_skills(self) -> str:
        """构建技能提示，拉取所有sill目录
        skill 具体内容并不放进提示词，保存在对话记录中
        """
        return "你拥有以下技能可用：\n" f"{self.skill_loader.describe_available()}\n"

    def _build_memory(self) -> str:
        """构建记忆提示，载入所有内容，注意memory在程序中会动态修改，每次需要重新构建
        涉及到缓存问题，后续优化
        """
        return "你拥有以下记忆可用：\n" f"{self.memory_manager.load_memory_prompt()}\n"

    # def _build_claude_md(self) -> str:
    #     return """
    #     You have the following claude md available:
    #     """

    # def _build_dynamic(self) -> str:
    #     """构建动态提示，例如技能、记忆等"""
    #     parts = []
    #     parts.append(self._build_skills())
    #     parts.append(self._build_memory())
    #     return "\n\n".join(p for p in parts if p)
