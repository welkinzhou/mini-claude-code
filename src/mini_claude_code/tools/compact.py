from dataclasses import dataclass
from typing import Any

from .base import ToolSpec
from .runner import ToolRunner

from anthropic import Anthropic


@dataclass(frozen=True, slots=True)
class CompactTool:
    client: Anthropic
    model_id: str

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="compact",
            description="Compact a list of messages.",
            input_schema={
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "What to preserve in the summary",
                    }
                },
            },
        )

    def run(self, _: Any, runner: ToolRunner) -> str:
        runner.pending_compact = True
        return "Compressing..."
