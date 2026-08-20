#!/usr/bin/env python3
"""校验 agri_backend_v2 skill.md YAML front matter 的统一契约。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
TOP_LEVEL_FIELDS = {
    "schema_version",
    "name",
    "kind",
    "mcp_tool",
    "risk_level",
    "finalize_after_success",
    "execution",
    "completion",
    "description",
    "triggers",
    "operations",
    "parameters",
}
OPERATION_FIELDS = {
    "tool_name",
    "description",
    "risk_level",
    "parameters",
    "required",
    "required_any",
    "mcp_tool",
    "inject_operation",
    "finalize_after_success",
    "expose_to_model",
    "approval_followup",
    "execution",
    "completion",
}
RISK_LEVELS = {"read", "write_confirm", "write_high", "mixed"}


def parse_front_matter(path: Path) -> dict[str, Any]:
    """解析一个 skill.md 的 YAML front matter。"""
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("缺少以 --- 包围的 YAML front matter")
    value = yaml.safe_load(match.group(1))
    if not isinstance(value, dict):
        raise ValueError("front matter 必须解析为对象")
    return value


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and item for item in value
    )


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
        _validate_completion(config.get("completion"), path, errors)
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


def validate_directory(skills_dir: Path) -> list[str]:
    errors: list[str] = []
    public_tools: dict[str, Path] = {}
    for path in sorted(skills_dir.glob("*/skill.md")):
        try:
            meta = parse_front_matter(path)
            errors.extend(validate_metadata(meta, str(path)))
            for config in (meta.get("operations") or {}).values():
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
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{path}: {exc}")
    return errors


def main() -> int:
    skills_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("agri_backend_v2/agent/skills")
    errors = validate_directory(skills_dir)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"skill metadata 校验通过: {len(list(skills_dir.glob('*/skill.md')))} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
