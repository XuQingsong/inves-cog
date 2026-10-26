"""Fixed task registry for the two approved models."""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import yaml

ALLOWED_MODELS = frozenset({"glm-5.3", "deepseek-v4.1-flash"})
DIFFICULT_TASKS = frozenset({"anomaly_candidates", "graph_seed_draft", "exposure_draft", "segment_mapping_draft"})
OTHER_TASKS = frozenset(
    {
        "entity_tagging",
        "news_card",
        "move_card",
        "info_fields_extraction",
        "dedupe_assist",
        "claim_extraction",
        "systemic_event_tag",
        "summary_oneliner",
        "news_translate",
    }
)


@dataclass(frozen=True)
class TaskSpec:
    tier: str
    model: str
    timeout_seconds: int
    retries: int
    failure_status: str


class Registry:
    def __init__(self, path: Path | str):
        path = Path(path)
        payload = yaml.safe_load(path.read_text())
        if not isinstance(payload, dict) or set(payload) != {"tasks"}:
            raise ValueError(f"{path}: I37: expected only the tasks mapping")
        tasks = payload["tasks"]
        if not isinstance(tasks, dict) or set(tasks) != DIFFICULT_TASKS | OTHER_TASKS:
            raise ValueError(f"{path}: I37: task names differ from README §3.8")
        parsed = {}
        for name, fields in tasks.items():
            timeout = 300 if name == "anomaly_candidates" else 900
            expected = (
                TaskSpec("difficult", "glm-5.3", timeout, 0, "待分析")
                if name in DIFFICULT_TASKS
                else TaskSpec("other", "deepseek-v4.1-flash", 120, 2, "抽取失败")
            )
            try:
                spec = TaskSpec(**fields)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: I37: invalid task {name}") from exc
            if spec != expected or spec.model not in ALLOWED_MODELS:
                raise ValueError(f"{path}: I37: routing mismatch for {name}")
            parsed[name] = spec
        self.tasks = MappingProxyType(parsed)

    def resolve(self, task: str) -> TaskSpec:
        try:
            return self.tasks[task]
        except KeyError as exc:
            raise ValueError(f"I37: unregistered task {task}") from exc
