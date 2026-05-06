from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillManifest:
    name: str
    description: str
    path: Path
    metadata: dict[str, str]
    allowed_tools: list[str]


@dataclass
class SkillDocument:
    manifest: SkillManifest
    body: str


@dataclass(slots=True)
class SkillLoader:
    """从 ``skill_dir`` 下递归加载 ``SKILL.md`` 文件。

    SKILL.md 的 frontmatter 描述技能元信息（name / description /
    allowed-tools / metadata 等），其余正文按 markdown 渲染，按需加载到 LLM 上下文。
    """

    skill_dir: Path
    documents: dict[str, SkillDocument] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.__load_all()

    def __load_all(self) -> None:
        if not self.skill_dir.exists():
            return
        for path in sorted(self.skill_dir.rglob("SKILL.md")):
            text = path.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", path.parent.name)
            description = meta.get("description", "No description")
            manifest = SkillManifest(
                name=name,
                description=description,
                path=path,
                metadata=meta.get("metadata", {}),
                allowed_tools=meta.get("allowed-tools", []),
            )
            self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())

    def _parse_frontmatter(self, text: str) -> tuple:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = yaml.safe_load(match.group(1)) or {}
        return meta, match.group(2)

    def describe_available(self) -> str:
        """获取所有技能简述。"""
        if not self.documents:
            return "(no skills available)"
        lines = []
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    def load_full_text(self, name: str) -> str:
        """加载完整技能正文，包裹成 ``<skill>...</skill>`` 块。"""
        document = self.documents.get(name)
        if not document:
            known = ", ".join(sorted(self.documents)) or "(none)"
            return f"Error: Unknown skill '{name}'. Available skills: {known}"

        return (
            f'<skill name="{document.manifest.name}">\n' f"{document.body}\n" "</skill>"
        )
