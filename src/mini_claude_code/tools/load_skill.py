from dataclasses import dataclass

from .base import JsonObject, ToolSpec
from mini_claude_code.skills import SkillLoader


@dataclass(frozen=True, slots=True)
class LoadSkillTool:
    skill_loader: SkillLoader

    @property
    def spec(self) -> ToolSpec:
        # 返回工具规范
        return ToolSpec(
            name="load_skill",
            description="Load specialized knowledge by name.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name to load"}
                },
                "required": ["name"],
            },
        )

    def run(self, tool_input: JsonObject, _: "ToolRunner") -> str:
        # 获取命令
        name = tool_input.get("name")
        if not isinstance(name, str):
            return "Error: Invalid input; expected {'name': string}"
        # 加载技能
        skill = self.skill_loader.get_content(name)
        return skill
