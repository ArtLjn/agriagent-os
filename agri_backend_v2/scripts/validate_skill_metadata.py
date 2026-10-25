#!/usr/bin/env python3
"""校验 agri_backend_v2 skill.md YAML front matter 的统一契约。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

# 支持直接执行脚本和作为测试模块导入，复用运行时字段定义，避免两份契约漂移。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.domains.harness.tools.base import CONTROL_METADATA_FIELDS, ROUTING_FIELDS

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
TOP_LEVEL_FIELDS = {
    *CONTROL_METADATA_FIELDS,
    "schema_version",
    "name",
    "kind",
    "mcp_tool",
    "risk_level",
    "finalize_after_success",
    "execution",
    "completion",
    "description",
    "routing",
    "triggers",
    "operations",
    "parameters",
}
OPERATION_FIELDS = {
    *CONTROL_METADATA_FIELDS,
    "tool_name",
    "description",
    "routing",
    "risk_level",
    "parameters",
    "required",
    "required_any",
    "mcp_tool",
    "inject_operation",
    "finalize_after_success",
    "expose_to_model",
    "approval_followup",
    "empty_result_policy",
    "execution",
    "completion",
}
RISK_LEVELS = {"read", "write_confirm", "write_high", "mixed"}
SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def parse_front_matter(path: Path) -> dict[str, Any]:
    """解析一个 skill.md 的 YAML front matter。"""
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("缺少以 --- 包围的 YAML front matter")
    value = yaml.safe_load(match.group(1))
    if not isinstance(value, dict):
        raise TypeError("front matter 必须解析为对象")
    return value


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and item for item in value
    )


def _validate_routing(meta: dict, source: str, errors: list[str]) -> None:
    """源码检查和操作展开前都拒绝无效的模型选择边界。"""
    routing = meta.get("routing", {})
    for field in CONTROL_METADATA_FIELDS:
        if field in meta and (
            not isinstance(meta[field], str) or not meta[field].strip()
        ):
            errors.append(f"{source}: {field} 必须是非空字符串")
    if not isinstance(routing, dict) or any(
        key not in ROUTING_FIELDS
        or not _is_string_list(value)
        or any(not item.strip() for item in value)
        for key, value in routing.items()
    ):
        errors.append(f"{source}: routing 必须使用支持的字段及非空字符串列表")


def validate_metadata(meta: dict[str, Any], source: str = "skill.md") -> list[str]:
    """返回契约错误；空列表表示通过。"""
    errors: list[str] = []
    unknown = set(meta) - TOP_LEVEL_FIELDS
    if unknown:
        errors.append(f"{source}: 顶层包含未知字段: {sorted(unknown)}")
    if meta.get("schema_version") != 1:
        errors.append(f"{source}: schema_version 必须为 1")
    if not isinstance(meta.get("name"), str) or not re.fullmatch(
        r"[a-z][a-z0-9_]*", meta.get("name", "")
    ):
        errors.append(f"{source}: name 必须是 snake_case")
    kind = meta.get("kind")
    if kind not in {"mcp", "local"}:
        errors.append(f"{source}: kind 必须是 mcp 或 local")
    if kind == "mcp" and not isinstance(meta.get("mcp_tool"), str):
        errors.append(f"{source}: kind=mcp 时 mcp_tool 必须是字符串")
    if kind == "local" and meta.get("mcp_tool") is not None:
        errors.append(f"{source}: kind=local 时 mcp_tool 必须为 null")
    if meta.get("risk_level") not in RISK_LEVELS:
        errors.append(f"{source}: risk_level 必须是 {sorted(RISK_LEVELS)} 之一")
    if "finalize_after_success" in meta and not isinstance(
        meta["finalize_after_success"], bool
    ):
        errors.append(f"{source}: finalize_after_success 必须是布尔值")
    _validate_execution(meta.get("execution"), source, errors)
    _validate_routing(meta, source, errors)
    _validate_completion(meta.get("completion"), source, errors)
    if (
        not isinstance(meta.get("description"), str)
        or not meta.get("description", "").strip()
    ):
        errors.append(f"{source}: description 不能为空")
    if not _is_string_list(meta.get("triggers")):
        errors.append(f"{source}: triggers 必须是非空字符串列表")

    parameters = meta.get("parameters")
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        errors.append(f"{source}: parameters.type 必须为 object")
        properties: dict[str, Any] = {}
    else:
        properties = parameters.get("properties") or {}
        if not isinstance(properties, dict):
            errors.append(f"{source}: parameters.properties 必须是对象")
            properties = {}
        required = parameters.get("required", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            errors.append(f"{source}: parameters.required 必须是字符串列表")
        else:
            missing_properties = set(required) - set(properties)
            if missing_properties:
                errors.append(
                    f"{source}: required 参数未定义: {sorted(missing_properties)}"
                )

    operations = meta.get("operations")
    if not isinstance(operations, dict):
        errors.append(f"{source}: operations 必须是对象")
        operations = {}
    operation_property = properties.get("operation") or {}
    allowed_operations = set(operation_property.get("enum") or [])
    if operations and not allowed_operations:
        errors.append(
            f"{source}: 声明 operations 时 parameters.operation.enum 不能为空"
        )
    unknown_operations = set(operations) - allowed_operations
    if unknown_operations:
        errors.append(
            f"{source}: operations 包含未声明的 operation: {sorted(unknown_operations)}"
        )
    for operation, config in operations.items():
        path = f"{source}: operations.{operation}"
        if not isinstance(config, dict):
            errors.append(f"{path} 必须是对象")
            continue
        unknown_fields = set(config) - OPERATION_FIELDS
        if unknown_fields:
            errors.append(f"{path} 包含未知字段: {sorted(unknown_fields)}")
        if config.get("risk_level") not in RISK_LEVELS - {"mixed"}:
            errors.append(f"{path}.risk_level 必须是 read/write_confirm/write_high")
        if "mcp_tool" in config and not isinstance(config["mcp_tool"], str):
            errors.append(f"{path}.mcp_tool 必须是字符串")
        for boolean_field in (
            "inject_operation",
            "finalize_after_success",
            "expose_to_model",
        ):
            if boolean_field in config and not isinstance(config[boolean_field], bool):
                errors.append(f"{path}.{boolean_field} 必须是布尔值")
        _validate_execution(config.get("execution"), path, errors)
        _validate_routing(config, path, errors)
        _validate_completion(config.get("completion"), path, errors)
        _validate_empty_result_policy(config.get("empty_result_policy"), path, errors)
        followup = config.get("approval_followup")
        if followup is not None:
            if not isinstance(followup, dict):
                errors.append(f"{path}.approval_followup 必须是对象")
            else:
                if not isinstance(followup.get("tool_name"), str) or not re.fullmatch(
                    r"[a-z][a-z0-9_]*", followup.get("tool_name", "")
                ):
                    errors.append(
                        f"{path}.approval_followup.tool_name 必须是 snake_case"
                    )
                if not _is_string_list(followup.get("arguments_from_result")):
                    errors.append(
                        f"{path}.approval_followup.arguments_from_result 必须是非空字符串列表"
                    )
        tool_name = config.get("tool_name")
        if not isinstance(tool_name, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", tool_name
        ):
            errors.append(f"{path}.tool_name 必须是 snake_case")
        if (
            not isinstance(config.get("description"), str)
            or not config.get("description", "").strip()
        ):
            errors.append(f"{path}.description 不能为空")
        for field_name in ("parameters", "required"):
            if not _is_string_list(config.get(field_name, [])):
                errors.append(f"{path}.{field_name} 必须是字符串列表")
        unknown_parameters = set(config.get("parameters", [])) - set(properties)
        if unknown_parameters:
            errors.append(f"{path}.parameters 未定义参数: {sorted(unknown_parameters)}")
        unknown_required = set(config.get("required", [])) - set(properties)
        if unknown_required:
            errors.append(f"{path}.required 未定义参数: {sorted(unknown_required)}")
        required_not_exposed = set(config.get("required", [])) - set(
            config.get("parameters", [])
        )
        if required_not_exposed:
            errors.append(
                f"{path}.required 未包含在 parameters: {sorted(required_not_exposed)}"
            )
        required_any = config.get("required_any", [])
        if not _is_string_list(required_any):
            errors.append(f"{path}.required_any 必须是字符串列表")
        unknown_required_any = set(required_any) - set(properties)
        if unknown_required_any:
            errors.append(
                f"{path}.required_any 未定义参数: {sorted(unknown_required_any)}"
            )
        required_any_not_exposed = set(required_any) - set(config.get("parameters", []))
        if required_any_not_exposed:
            errors.append(
                f"{path}.required_any 未包含在 parameters: "
                f"{sorted(required_any_not_exposed)}"
            )
    return errors


def _validate_execution(execution: Any, source: str, errors: list[str]) -> None:
    """校验 Skill/operation 的执行能力声明。"""
    if execution is None:
        return
    if not isinstance(execution, dict):
        errors.append(f"{source}: execution 必须是对象")
        return
    mode = execution.get("mode", "serial")
    if mode not in {
        "serial",
        "parallel_safe",
        "serial_after_observation",
        "internal_followup",
    }:
        errors.append(f"{source}: execution.mode 不受支持: {mode}")
    max_concurrency = execution.get("max_concurrency", 1)
    if (
        not isinstance(max_concurrency, int)
        or isinstance(max_concurrency, bool)
        or max_concurrency < 1
    ):
        errors.append(f"{source}: execution.max_concurrency 必须是正整数")
    if "requires_observation" in execution and not isinstance(
        execution["requires_observation"], bool
    ):
        errors.append(f"{source}: execution.requires_observation 必须是布尔值")
    depends_on = execution.get("depends_on", [])
    if not _is_string_list(depends_on):
        errors.append(f"{source}: execution.depends_on 必须是字符串列表")


def _validate_completion(completion: Any, source: str, errors: list[str]) -> None:
    """校验成功后的收尾能力声明。"""
    if completion is None:
        return
    if not isinstance(completion, dict):
        errors.append(f"{source}: completion 必须是对象")
        return
    value = completion.get("finalize_after_success")
    if value is not None and not isinstance(value, bool):
        errors.append(f"{source}: completion.finalize_after_success 必须是布尔值")


def _validate_empty_result_policy(
    policy: Any, source: str, errors: list[str]
) -> None:
    """校验 operation 级空结果策略的封闭结构。"""
    if policy is None:
        return
    if not isinstance(policy, dict):
        errors.append(f"{source}.empty_result_policy 必须是对象")
        return
    unknown = set(policy) - {
        "observation",
        "next_allowed_action",
        "task_state",
        "trace",
    }
    if unknown:
        errors.append(f"{source}.empty_result_policy 包含未知字段: {sorted(unknown)}")
    for key in ("observation", "next_allowed_action", "task_state"):
        if key not in policy:
            errors.append(f"{source}.empty_result_policy.{key} 必填")
    observation = policy.get("observation")
    if observation is not None:
        if not isinstance(observation, dict):
            errors.append(f"{source}.empty_result_policy.observation 必须是对象")
        else:
            unknown = set(observation) - {"code", "message", "missing"}
            if unknown:
                errors.append(
                    f"{source}.empty_result_policy.observation 包含未知字段: "
                    f"{sorted(unknown)}"
                )
            if not isinstance(observation.get("code"), str) or not SNAKE_CASE_RE.fullmatch(
                observation.get("code", "")
            ):
                errors.append(
                    f"{source}.empty_result_policy.observation.code 必须是 snake_case"
                )
            if (
                not isinstance(observation.get("message"), str)
                or not observation.get("message", "").strip()
            ):
                errors.append(
                    f"{source}.empty_result_policy.observation.message 不能为空"
                )
            if not _is_string_list(observation.get("missing", [])):
                errors.append(
                    f"{source}.empty_result_policy.observation.missing "
                    "必须是字符串列表"
                )
    next_action = policy.get("next_allowed_action")
    if next_action is not None:
        if not isinstance(next_action, dict):
            errors.append(f"{source}.empty_result_policy.next_allowed_action 必须是对象")
        else:
            unknown = set(next_action) - {"agent_tool_name", "arguments"}
            if unknown:
                errors.append(
                    f"{source}.empty_result_policy.next_allowed_action 包含未知字段: "
                    f"{sorted(unknown)}"
                )
            if not isinstance(
                next_action.get("agent_tool_name"), str
            ) or not SNAKE_CASE_RE.fullmatch(next_action.get("agent_tool_name", "")):
                errors.append(
                    f"{source}.empty_result_policy.next_allowed_action."
                    "agent_tool_name 必须是 snake_case"
                )
            if "arguments" not in next_action:
                errors.append(
                    f"{source}.empty_result_policy.next_allowed_action.arguments "
                    "必须显式声明"
                )
            elif next_action["arguments"] is not None and not isinstance(
                next_action["arguments"], dict
            ):
                errors.append(
                    f"{source}.empty_result_policy.next_allowed_action.arguments "
                    "必须是 null 或对象"
                )
    task_state = policy.get("task_state")
    if task_state is not None:
        if not isinstance(task_state, dict):
            errors.append(f"{source}.empty_result_policy.task_state 必须是对象")
        else:
            unknown = set(task_state) - {"reason", "resume_policy"}
            if unknown:
                errors.append(
                    f"{source}.empty_result_policy.task_state 包含未知字段: "
                    f"{sorted(unknown)}"
                )
            if not isinstance(task_state.get("reason"), str) or not SNAKE_CASE_RE.fullmatch(
                task_state.get("reason", "")
            ):
                errors.append(
                    f"{source}.empty_result_policy.task_state.reason 必须是 snake_case"
                )
            if task_state.get("resume_policy") != "ask_user":
                errors.append(
                    f"{source}.empty_result_policy.task_state.resume_policy "
                    "必须是 ask_user"
                )
    trace = policy.get("trace")
    if trace is not None:
        if not isinstance(trace, dict):
            errors.append(f"{source}.empty_result_policy.trace 必须是对象")
        else:
            unknown = set(trace) - {"progress_reason"}
            if unknown:
                errors.append(
                    f"{source}.empty_result_policy.trace 包含未知字段: "
                    f"{sorted(unknown)}"
                )
            reason = trace.get("progress_reason")
            if not isinstance(reason, str) or not SNAKE_CASE_RE.fullmatch(reason):
                errors.append(
                    f"{source}.empty_result_policy.trace.progress_reason "
                    "必须是 snake_case"
                )


def _scan_directory(
    skills_dir: Path,
    errors: list[str],
    public_tools: dict[str, Path],
    exposed_tools: dict[str, bool],
    policies: list[tuple[str, str | None, str]],
) -> None:
    """扫描单个目录并累计公开工具和空结果策略目标。"""
    for path in sorted(skills_dir.glob("*/skill.md")):
        try:
            meta = parse_front_matter(path)
            errors.extend(validate_metadata(meta, str(path)))
            for operation, config in (meta.get("operations") or {}).items():
                if not isinstance(config, dict):
                    continue
                tool_name = config.get("tool_name")
                if not isinstance(tool_name, str):
                    continue
                previous = public_tools.get(tool_name)
                if previous is not None:
                    errors.append(
                        f"{path}: 公开 tool_name {tool_name} 与 {previous} 重复"
                    )
                else:
                    public_tools[tool_name] = path
                exposed_tools[tool_name] = config.get("expose_to_model", True) is not False
                policy = config.get("empty_result_policy")
                if isinstance(policy, dict):
                    next_action = policy.get("next_allowed_action")
                    target = (
                        next_action.get("agent_tool_name")
                        if isinstance(next_action, dict)
                        else None
                    )
                    policies.append(
                        (f"{path}: operations.{operation}", tool_name, str(target or ""))
                    )
        except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
            errors.append(f"{path}: {exc}")


def validate_directories(skills_dirs: list[Path]) -> list[str]:
    """跨目录校验公开 tool_name 唯一性与空结果策略目标。"""
    errors: list[str] = []
    public_tools: dict[str, Path] = {}
    exposed_tools: dict[str, bool] = {}
    policies: list[tuple[str, str | None, str]] = []
    for skills_dir in skills_dirs:
        _scan_directory(
            skills_dir, errors, public_tools, exposed_tools, policies
        )
    for source, own_tool, target in policies:
        if not target:
            continue
        if target not in public_tools:
            errors.append(
                f"{source}.empty_result_policy.next_allowed_action.agent_tool_name "
                f"未注册: {target}"
            )
            continue
        if target == own_tool:
            errors.append(
                f"{source}.empty_result_policy.next_allowed_action 不能指向自身"
            )
        if not exposed_tools.get(target, True):
            errors.append(
                f"{source}.empty_result_policy.next_allowed_action 目标未暴露: {target}"
            )
    return errors


def validate_directory(skills_dir: Path) -> list[str]:
    return validate_directories([skills_dir])


def _default_skill_dirs() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    directories = [root / "agent" / "tools"]
    directories.extend(
        sorted(
            path
            for path in (root / "businesses").glob("*/skills")
            if not path.parent.name.startswith(("_", "."))
        )
    )
    return directories


def main() -> int:
    directories = (
        [Path(sys.argv[1])] if len(sys.argv) > 1 else _default_skill_dirs()
    )
    errors = validate_directories(directories)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    total = sum(len(list(directory.glob("*/skill.md"))) for directory in directories)
    print(f"skill metadata 校验通过: {total} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
