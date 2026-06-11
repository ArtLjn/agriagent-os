"""Skill Catalog 构建。"""

import json

from langchain_core.tools import BaseTool

from app.agent.router.models import ToolCandidate
from app.agent.router.registry import CATALOG_REGISTRY, default_risk_for_tool
from app.agent.tool_selection_rules import DISABLED_SKILLS


def _safe_text(value) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return ""
    return str(value)


def _json_safe_payload(value):
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        return ""


def _args_schema_payload(tool: BaseTool) -> dict | str:
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        return ""
    for method_name in ("model_json_schema", "schema"):
        schema_method = getattr(args_schema, method_name, None)
        if schema_method is None:
            continue
        try:
            schema_payload = schema_method()
            return _json_safe_payload(schema_payload)
        except (TypeError, ValueError, AttributeError):
            continue
    return ""


def _schema_token_estimate(tool: BaseTool) -> int:
    payload = {
        "name": _safe_text(getattr(tool, "name", "")),
        "description": _safe_text(getattr(tool, "description", "")),
        "args_schema": _args_schema_payload(tool),
    }
    return max(80, len(json.dumps(payload, ensure_ascii=False)) // 2)


def _tool_enabled(tool: BaseTool) -> bool:
    metadata = getattr(tool, "skill_metadata", None)
    enabled = getattr(metadata, "enabled", None)
    if isinstance(enabled, bool):
        return enabled
    return tool.name not in DISABLED_SKILLS


class SkillCatalog:
    """按名称访问的 Skill Catalog。"""

    def __init__(self, candidates: list[ToolCandidate]) -> None:
        self._by_name = {candidate.name: candidate for candidate in candidates}

    @classmethod
    def from_tools(cls, tools: list[BaseTool]) -> "SkillCatalog":
        candidates = []
        for tool in tools:
            name = _safe_text(getattr(tool, "name", ""))
            override = CATALOG_REGISTRY.get(name, {})
            candidates.append(
                ToolCandidate(
                    name=name,
                    domain=override.get("domain", "general"),
                    intents=list(override.get("intents", [name])),
                    risk=override.get("risk", default_risk_for_tool(name)),
                    entities=list(override.get("entities", [])),
                    trigger_examples=list(override.get("trigger_examples", [])),
                    anti_examples=list(override.get("anti_examples", [])),
                    context_dependencies=list(override.get("context_dependencies", [])),
                    candidate_group=override.get("candidate_group", "general"),
                    schema_token_estimate=_schema_token_estimate(tool),
                    enabled=_tool_enabled(tool),
                )
            )
        return cls(candidates)

    def get(self, name: str) -> ToolCandidate | None:
        return self._by_name.get(name)

    def enabled(self) -> list[ToolCandidate]:
        return [candidate for candidate in self._by_name.values() if candidate.enabled]

    def names(self) -> list[str]:
        return list(self._by_name)
