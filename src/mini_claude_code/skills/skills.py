from dataclasses import dataclass, field

from pathlib import Path

import re
import yaml
from mini_claude_code.utils import get_workdir

SKILL_DIR = get_workdir() / "skills"


@dataclass(slots=True)
class SkillLoader:
    skill_dir: Path = field(default_factory=lambda: SKILL_DIR)
    skills: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.__load_all()

    def __load_all(self) -> None:
        if not self.skill_dir.exists():
            return
        for skill_file in sorted(self.skill_dir.rglob("SKILL.md")):
            # SKILL.md 文件中包含技能的名称、描述、参数、返回值等信息
            # 元数据使用yaml格式
            # ---
            # name: 技能名称
            # description: 技能描述
            # parameters:
            #     - name: 参数名称
            #     - description: 参数描述
            #     - type: 参数类型
            #     - required: 是否必填
            # ---
            # 其余部分使用 markdown 格式
            # 初始化只需要解析元数据
            # 用到的时候再解析其余部分
            # 添加进 llm 上下文
            text = skill_file.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", skill_file.parent.name)
            self.skills[name] = {"meta": meta, "body": body, "path": str(skill_file)}

    def _parse_frontmatter(self, text: str) -> tuple:
        """Parse YAML frontmatter between --- delimiters."""
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        return meta, match.group(2).strip()

    def get_descriptions(self) -> str:
        """Layer 1: short descriptions for the system prompt."""
        if not self.skills:
            return "(no skills available)"
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)
        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        """Layer 2: full skill body returned in tool_result."""
        skill = self.skills.get(name)
        if not skill:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills.keys())}"
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"
