"""Skill 基类和 SkillResult 数据结构。

所有 skill 继承 Skill 基类，实现 execute() 方法。
统一接口让 react.py 不关心是 mcp 还是 local。

元数据（name/description/parameters_schema）由 skill.md YAML front matter
定义，loader 在加载时注入。Python 类只需实现自定义逻辑（execute / dynamic_risk_level）。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

_REQUIRED_ANY_MARKER = "__required_any__"

if TYPE_CHECKING:
    from agent.domains.harness.tools.context import SkillContext


@dataclass
class SkillResult:
    """Skill 执行结果。"""

    data: Any = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Skill:
    """Skill 基类。

    元数据由 loader 从 skill.md 注入（_meta dict），属性方法优先读 _meta。
    子类只需实现自定义逻辑（execute / dynamic_risk_level）。

    kind:
      - "mcp"   → execute() 内部用 ctx.business_client.call_tool(...)
      - "local" → execute() 内部直接计算或调第三方
    """

    kind: str = "mcp"
    mcp_tool: str = ""

    # loader 从 skill.md 注入的元数据
    _meta: ClassVar[dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return self._meta.get("name", "")

    @property
    def description(self) -> str:
        return self._meta.get("description", "")

    @property
    def risk_level(self) -> str:
        return self._meta.get("risk_level", "read")

    @property
    def finalize_after_success(self) -> bool:
        """成功执行后是否应立即进入无工具最终回答。"""
        completion = self._meta.get("completion") or {}
        if isinstance(completion, dict) and "finalize_after_success" in completion:
            return completion["finalize_after_success"] is True
        return self._meta.get("finalize_after_success") is True

    @property
    def parallel_safe(self) -> bool:
        """判断只读 Skill 是否可以与同轮同伴共享一次推理步骤。

        并行能力必须由 skill.md 显式声明；缺少 execution 配置时默认串行。
        """
        return (
            self.execution_mode == "parallel_safe"
            and self.risk_level == "read"
            and not self.finalize_after_success
            and not self.requires_observation
            and not self.depends_on
        )

    @property
    def execution_mode(self) -> str:
        """返回声明的执行模式；未声明时 fail-closed 为串行。"""
        execution = self._meta.get("execution") or {}
        if not isinstance(execution, dict):
            return "serial"
        return str(execution.get("mode") or "serial")

    @property
    def max_concurrency(self) -> int:
        """返回单个 Skill 的并发上限。"""
        execution = self._meta.get("execution") or {}
        value = (
            execution.get("max_concurrency", 1) if isinstance(execution, dict) else 1
        )
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
            else 1
        )

    @property
    def requires_observation(self) -> bool:
        """声明该 Skill 是否必须等待上一批 Observation。"""
        execution = self._meta.get("execution") or {}
        return bool(
            execution.get("requires_observation", False)
            if isinstance(execution, dict)
            else False
        )

    @property
    def depends_on(self) -> tuple[str, ...]:
        """返回执行策略声明的依赖名称。"""
        execution = self._meta.get("execution") or {}
        depends_on = (
            execution.get("depends_on", []) if isinstance(execution, dict) else []
        )
        if not isinstance(depends_on, list):
            return ()
        return tuple(str(item) for item in depends_on if isinstance(item, str) and item)

    @property
    def exposed(self) -> bool:
        """是否作为独立工具暴露给模型。

        聚合 skill 中由 Runtime 自动驱动的后继动作（如 commit_planting_plan）
        设 expose_to_model=false，模型看不到它，避免重建提交参数。
        """
        return True

    @property
    def approval_followup(self) -> dict[str, Any] | None:
        """prepare 类只读动作返回 ready 后，Runtime 应自动驱动的后继写动作。

        来自 operation 配置的 approval_followup 字段，形如：
            {tool_name: commit_planting_plan,
             arguments_from_result: [client_request_id, approval_fingerprint, plan]}
        仅 OperationSkill 覆盖；普通 Skill 返回 None。
        """
        return None

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据实际参数返回风险等级。

        默认实现：risk_level 为 "mixed" 时根据 operation 判断，
        否则直接返回 risk_level。子类可覆盖。
        """
        base = self.risk_level
        if base != "mixed":
            return base
        op = (params.get("operation") or "").lower()
        configured_risk = self._operation_config(op).get("risk_level")
        if configured_risk:
            return configured_risk
        if op in ("create", "update", "advance", "repay", "settle"):
            return "write_confirm"
        if op == "delete":
            return "write_high"
        return "read"

    def enrich_params(self, params: dict[str, Any], ctx) -> dict[str, Any]:
        """返回调用参数副本；业务语义解析由模型根据工具 schema 完成。"""
        return self._with_schema_defaults(params)

    def _with_schema_defaults(self, params: dict[str, Any]) -> dict[str, Any]:
        """物化 schema 默认值，确保重复调用比较的是有效参数。"""
        enriched = dict(params)
        properties = self.parameters_schema.get("properties") or {}
        for name, schema in properties.items():
            if (
                name not in enriched
                and isinstance(schema, dict)
                and "default" in schema
            ):
                enriched[name] = deepcopy(schema["default"])
        return enriched

    def _operation_config(self, operation: str | None) -> dict[str, Any]:
        """读取统一 operations 配置。"""
        operations = self._meta.get("operations") or {}
        if isinstance(operations, dict) and isinstance(operations.get(operation), dict):
            return operations[operation]
        return {}

    def missing_required_params(self, params: dict[str, Any]) -> list[str]:
        """返回 schema 及 operation 条件下缺失的参数名。

        聚合 skill 兼容内部调用时读取 operation.required；面向模型的
        OperationSkill 已把该动作的 required 直接投影到公开 schema。
        """
        required = self.parameters_schema.get("required") or []
        operation = params.get("operation")
        conditional = self._operation_config(operation).get("required") or []

        missing: list[str] = []
        for name in [*required, *conditional]:
            if name not in missing and params.get(name) in (None, ""):
                missing.append(name)
        required_any = self.required_any_params(operation)
        if required_any and not any(
            params.get(name) not in (None, "") for name in required_any
        ):
            missing.append(_REQUIRED_ANY_MARKER)
        return missing

    def required_any_params(self, operation: str | None = None) -> list[str]:
        """返回条件约束中至少需要提供一个的参数名。"""
        operation_config = self._operation_config(operation)
        if not operation_config:
            operation_config = getattr(self, "_operation_config_meta", {})
        required_any = operation_config.get("required_any") or []
        if not isinstance(required_any, list):
            return []
        return [name for name in required_any if isinstance(name, str) and name]

    def missing_params_prompt(self, missing: list[str]) -> str:
        """生成业务信息缺失说明，不暴露内部 operation。"""
        properties = self.parameters_schema.get("properties") or {}
        details: list[str] = []
        if _REQUIRED_ANY_MARKER in missing:
            required_any = self.required_any_params()
            choices = [
                str((properties.get(name) or {}).get("description") or name)
                for name in required_any
            ]
            details.append("至少提供以下一项：" + "、".join(choices))
        details.extend(
            str((properties.get(name) or {}).get("description") or "必要业务信息")
            for name in missing
            if name != _REQUIRED_ANY_MARKER
        )
        return "缺少完成该业务动作所需的信息：" + "；".join(details)

    @property
    def parameters_schema(self) -> dict:
        return self._meta.get(
            "parameters", {"type": "object", "properties": {}, "required": []}
        )

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        """执行 skill。子类必须实现（或 kind=mcp 时由 McpSkill 提供默认实现）。"""
        raise NotImplementedError

    def to_openai_tool(self) -> dict:
        """转换为 OpenAI tools schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self._tool_description(),
                "parameters": self.parameters_schema,
            },
        }

    def _tool_description(self) -> str:
        """返回面向模型的业务描述，不投影 Business MCP 内部协议。"""
        return self.description

    def operation_skills(self) -> list[OperationSkill]:
        """把聚合 skill 展开为模型可直接选择的单一动作 skill。"""
        operations = self._meta.get("operations") or {}
        if not isinstance(operations, dict):
            return []
        return [OperationSkill(self, operation) for operation in operations]


class McpSkill(Skill):
    """通用 MCP skill：execute() 直接调 business MCP tool。

    用于纯 MCP 代理 skill（无自定义逻辑），loader 从 skill.md 自动创建。
    有自定义逻辑的 skill 应继承 Skill 而非 McpSkill。
    """

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        enriched = self.enrich_params(params, ctx)
        missing = self.missing_required_params(enriched)
        if missing:
            return SkillResult(error=self.missing_params_prompt(missing))
        result = await ctx.call_mcp_tool(
            self.mcp_tool,
            enriched,
            risk_level=self.dynamic_risk_level(enriched),
        )
        if isinstance(result, dict) and result.get("error"):
            message = str(result.get("message") or result["error"])
            return SkillResult(data=result, error=message)
        return SkillResult(data=result)


class OperationSkill(McpSkill):
    """Agent-facing MCP skill，固定一个 operation 并在执行时注入它。"""

    def __init__(self, source: Skill, operation: str) -> None:
        self._source = source
        self.operation = operation
        source_config = source._meta.get("operations", {}).get(operation, {})
        self._meta = deepcopy(source._meta)
        self._meta["name"] = (
            source_config.get("tool_name") or f"{source.name}_{operation}"
        )
        self._meta["description"] = (
            source_config.get("description") or source.description
        )
        self._meta["risk_level"] = source_config.get("risk_level") or source.risk_level
        source_execution = source._meta.get("execution")
        operation_execution = source_config.get("execution")
        if isinstance(source_execution, dict) or isinstance(operation_execution, dict):
            self._meta["execution"] = {
                **(source_execution if isinstance(source_execution, dict) else {}),
                **(
                    operation_execution if isinstance(operation_execution, dict) else {}
                ),
            }
        source_completion = source._meta.get("completion")
        operation_completion = source_config.get("completion")
        if isinstance(source_completion, dict) or isinstance(
            operation_completion, dict
        ):
            self._meta["completion"] = {
                **(source_completion if isinstance(source_completion, dict) else {}),
                **(
                    operation_completion
                    if isinstance(operation_completion, dict)
                    else {}
                ),
            }
        if "finalize_after_success" in source_config:
            self._meta["finalize_after_success"] = source_config[
                "finalize_after_success"
            ]
        self._meta["operations"] = {}
        self.kind = source.kind
        operation_mcp_tool = source_config.get("mcp_tool")
        self.mcp_tool = (
            operation_mcp_tool.rsplit(".", 1)[-1]
            if isinstance(operation_mcp_tool, str)
            else source.mcp_tool
        )
        self._inject_operation = source_config.get("inject_operation", True)

        source_schema = source.parameters_schema
        source_properties = source_schema.get("properties") or {}
        exposed = source_config.get("parameters")
        if isinstance(exposed, list):
            property_names = exposed
        else:
            property_names = [name for name in source_properties if name != "operation"]
        properties = {
            name: deepcopy(source_properties[name])
            for name in property_names
            if name in source_properties
        }
        required = source_config.get("required") or []
        self._meta["parameters"] = {
            "type": "object",
            "properties": properties,
            "required": [name for name in required if name in properties],
        }
        self._operation_config_meta = source_config

    def enrich_params(self, params: dict[str, Any], ctx) -> dict[str, Any]:
        return self._with_schema_defaults(params)

    @property
    def exposed(self) -> bool:
        return self._operation_config_meta.get("expose_to_model", True)

    @property
    def approval_followup(self) -> dict[str, Any] | None:
        return self._operation_config_meta.get("approval_followup")

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        return self._operation_config_meta.get(
            "risk_level"
        ) or self._source.dynamic_risk_level({**params, "operation": self.operation})

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        enriched = self.enrich_params(params, ctx)
        missing = self.missing_required_params(enriched)
        if missing:
            return SkillResult(error=self.missing_params_prompt(missing))
        call_args = dict(enriched)
        if self._inject_operation:
            call_args["operation"] = self.operation
        result = await ctx.call_mcp_tool(
            self.mcp_tool,
            call_args,
            risk_level=self.dynamic_risk_level(enriched),
        )
        if isinstance(result, dict) and result.get("error"):
            message = str(result.get("message") or result["error"])
            return SkillResult(data=result, error=message)
        return SkillResult(data=result)
