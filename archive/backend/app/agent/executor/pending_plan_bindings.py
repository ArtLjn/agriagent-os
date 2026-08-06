"""Pending plan step 参数绑定解析。"""

from typing import Any


def resolve_step_param_bindings(
    params: dict,
    results_by_step: dict[str, object],
) -> dict:
    """解析 pending plan 参数中的前序步骤输出绑定。"""
    return {
        key: _resolve_binding_value(value, results_by_step)
        for key, value in (params or {}).items()
    }


def _resolve_binding_value(value, results_by_step: dict[str, object]):
    if isinstance(value, dict) and "$from_step" in value:
        source_step = str(value.get("$from_step") or "").strip()
        if not source_step:
            raise ValueError("参数绑定缺少来源步骤。")
        if source_step not in results_by_step:
            raise ValueError(f"参数绑定引用的步骤“{source_step}”尚未成功执行。")

        path = str(value.get("path") or "id").strip()
        try:
            return _read_result_path(results_by_step[source_step], path)
        except ValueError as exc:
            raise ValueError(f"参数绑定引用失败：步骤“{source_step}”的{exc}") from exc

    if isinstance(value, dict):
        return {
            key: _resolve_binding_value(item, results_by_step)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_binding_value(item, results_by_step) for item in value]
    return value


def _read_result_path(result, path: str):
    segments = [segment for segment in str(path or "").split(".") if segment]
    if not segments:
        raise ValueError("结果路径不能为空。")

    current = result
    for segment in segments:
        current = _read_result_segment(current, segment)
        if current is None:
            raise ValueError(f"结果中缺少路径“{path}”。")
    return current


def _read_result_segment(current, segment: str) -> Any:
    if isinstance(current, dict):
        if segment in current:
            return current[segment]
        raise ValueError(f"结果中缺少字段“{segment}”。")

    if isinstance(current, list) and segment.isdigit():
        index = int(segment)
        if 0 <= index < len(current):
            return current[index]
        raise ValueError(f"结果中缺少字段“{segment}”。")

    if hasattr(current, segment):
        return getattr(current, segment)

    data = getattr(current, "data", None)
    if isinstance(data, dict) and segment in data:
        return data[segment]

    raise ValueError(f"结果中缺少字段“{segment}”。")
