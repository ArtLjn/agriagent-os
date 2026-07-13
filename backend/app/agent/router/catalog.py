"""Skill Catalog 构建。"""

import json
from dataclasses import replace

from langchain_core.tools import BaseTool

from app.agent.router.models import ToolCandidate
from app.agent.router.registry import CATALOG_REGISTRY, default_risk_for_tool
from app.agent.skills.registry import (
    AliasDefinition,
    CapabilityDefinition,
    OperationDefinition,
    SkillRegistry,
    load_skill_registry,
)
from app.agent.tool_selection_rules import DISABLED_SKILLS


_ROUTER_READ_RISKS = frozenset({"read", "external_network"})
_WRITE_RISKS = frozenset({"write_confirm", "write_high"})
_REGISTRY: SkillRegistry | None = None


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


def _load_registry() -> SkillRegistry | None:
    global _REGISTRY
    if _REGISTRY is None:
        try:
            _REGISTRY = load_skill_registry()
        except (OSError, ValueError):
            return None
    return _REGISTRY


def _registry_parts(
    name: str,
) -> (
    tuple[SkillRegistry, AliasDefinition, CapabilityDefinition, OperationDefinition]
    | None
):
    registry = _load_registry()
    if registry is None:
        return None
    alias = registry.resolve_alias(name)
    if alias is None:
        return None
    capability = registry.capabilities.get(alias.capability)
    operation = registry.get_operation(alias.capability, alias.operation)
    if capability is None or operation is None:
        return None
    return registry, alias, capability, operation


def _capability_parts(name: str) -> tuple[SkillRegistry, CapabilityDefinition] | None:
    registry = _load_registry()
    if registry is None:
        return None
    capability = registry.capabilities.get(name)
    if capability is None:
        return None
    return registry, capability


def _catalog_payload(name: str) -> dict:
    parts = _registry_parts(name)
    if parts is None:
        capability_parts = _capability_parts(name)
        if capability_parts is None:
            return CATALOG_REGISTRY.get(name, {})
        _registry, capability = capability_parts
        return {
            "domain": capability.domain,
            "intents": [
                capability.name,
                capability.capability,
                *list(capability.tags),
                *list(capability.operations),
                *[
                    legacy
                    for operation in capability.operations.values()
                    for legacy in operation.legacy_aliases
                ],
            ],
            "risk": "read",
            "capability": capability.name,
            "operation": None,
            "legacy_alias": None,
            "operation_risk": None,
            "entities": list(capability.tags),
            "trigger_examples": list(capability.examples),
            "anti_examples": list(capability.anti_examples),
            "context_dependencies": list(capability.context_dependencies),
            "candidate_group": f"{capability.domain}_capability",
            "enabled": capability.status == "active",
            "score": 1.0,
            "evidence": {
                "source": "skill_registry",
                "domain": capability.domain,
                "capability": capability.name,
            },
        }
    _registry, alias, capability, operation = parts
    risk = _router_risk(operation.risk)
    return {
        "domain": capability.domain,
        "intents": [alias.operation, alias.capability, capability.capability, name],
        "risk": risk,
        "capability": alias.capability,
        "operation": alias.operation,
        "legacy_alias": alias.legacy_name,
        "operation_risk": operation.risk,
        "entities": list(capability.tags),
        "trigger_examples": list(capability.examples),
        "anti_examples": list(capability.anti_examples),
        "context_dependencies": list(capability.context_dependencies),
        "candidate_group": f"{capability.domain}_{risk}",
        "enabled": capability.status == "active",
        "score": 1.0,
        "evidence": {
            "source": "skill_registry",
            "domain": capability.domain,
            "capability": alias.capability,
            "operation": alias.operation,
            "legacy_alias": alias.legacy_name,
            "operation_risk": operation.risk,
        },
    }


def _router_risk(operation_risk: str) -> str:
    if operation_risk in _WRITE_RISKS:
        return operation_risk
    if operation_risk in _ROUTER_READ_RISKS:
        return "read"
    return "read"


def _candidate_enabled(tool: BaseTool, payload: dict) -> bool:
    metadata_enabled = getattr(getattr(tool, "skill_metadata", None), "enabled", None)
    if isinstance(metadata_enabled, bool):
        return metadata_enabled
    enabled = payload.get("enabled")
    if isinstance(enabled, bool):
        return enabled and _tool_enabled(tool)
    return _tool_enabled(tool)


class SkillCatalog:
    """按名称访问的 Skill Catalog。"""

    def __init__(self, candidates: list[ToolCandidate]) -> None:
        self._by_name = {candidate.name: candidate for candidate in candidates}
        self._by_alias = self._build_alias_index(candidates)

    @staticmethod
    def _build_alias_index(
        candidates: list[ToolCandidate],
    ) -> dict[str, ToolCandidate]:
        registry = _load_registry()
        if registry is None:
            return {}
        by_alias: dict[str, ToolCandidate] = {}
        by_capability = {
            candidate.capability: candidate
            for candidate in candidates
            if candidate.capability
        }
        for capability_name, candidate in by_capability.items():
            capability = registry.capabilities.get(capability_name)
            if capability is None:
                continue
            for operation in capability.operations.values():
                for legacy_alias in operation.legacy_aliases:
                    by_alias[legacy_alias] = replace(
                        candidate,
                        operation=operation.name,
                        legacy_alias=legacy_alias,
                        operation_risk=operation.risk,
                        risk=_router_risk(operation.risk),
                        candidate_group=(
                            f"{capability.domain}_{_router_risk(operation.risk)}"
                        ),
                        evidence={
                            **candidate.evidence,
                            "operation": operation.name,
                            "legacy_alias": legacy_alias,
                            "operation_risk": operation.risk,
                        },
                    )
        return by_alias

    @classmethod
    def from_tools(cls, tools: list[BaseTool]) -> "SkillCatalog":
        candidates = []
        for tool in tools:
            name = _safe_text(getattr(tool, "name", ""))
            override = _catalog_payload(name)
            candidates.append(
                ToolCandidate(
                    name=name,
                    domain=override.get("domain", "general"),
                    intents=list(override.get("intents", [name])),
                    risk=override.get("risk", default_risk_for_tool(name)),
                    capability=override.get("capability"),
                    operation=override.get("operation"),
                    legacy_alias=override.get("legacy_alias", name),
                    operation_risk=override.get("operation_risk"),
                    entities=list(override.get("entities", [])),
                    trigger_examples=list(override.get("trigger_examples", [])),
                    anti_examples=list(override.get("anti_examples", [])),
                    context_dependencies=list(override.get("context_dependencies", [])),
                    candidate_group=override.get("candidate_group", "general"),
                    schema_token_estimate=_schema_token_estimate(tool),
                    enabled=_candidate_enabled(tool, override),
                    score=float(override.get("score", 0.0)),
                    evidence=dict(override.get("evidence", {})),
                )
            )
        return cls(candidates)

    def get(self, name: str) -> ToolCandidate | None:
        return self._by_name.get(name) or self._by_alias.get(name)

    def enabled(self) -> list[ToolCandidate]:
        return [candidate for candidate in self._by_name.values() if candidate.enabled]

    def candidates(self) -> list[ToolCandidate]:
        return list(self._by_name.values())

    def names(self) -> list[str]:
        return list(self._by_name)
