from dataclasses import dataclass

from mini_claude_code.runtime.tool_spec import JsonObject, ToolSpec
from mini_claude_code.providers.skills import SkillLoader


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

    def run(self, tool_input: JsonObject, _context=None) -> str:
        name = tool_input.get("name")
        if not isinstance(name, str):
            return "Error: Invalid input; expected {'name': string}"
        # 加载技能
        skill = self.skill_loader.load_full_text(name)
        return skill
