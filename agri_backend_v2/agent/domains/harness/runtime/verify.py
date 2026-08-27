"""Verification 层：ProgressLedger + Doom Loop 检测 + 完成前 checklist。

参考：harness_study/_example/tools/verify.py + tools/safety.py

合并原因：safety.py 的 detect_doom_loop 和 verify.py 的 CallTracker
都是"防止 agent 重复犯错"的同一关注点，合并到单文件避免碎片化。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

# ─── ProgressLedger ──────────────────────────────────────────

# 滑动窗口大小（看最近 N 次调用判断是否死循环）
DOOM_LOOP_WINDOW = 5
# 同一 (skill, args) 出现 >= N 次视为死循环
DUPLICATE_THRESHOLD = 3
_VOLATILE_RESULT_KEYS = {
    "attempt",
    "duration_ms",
    "request_id",
    "trace_id",
    "timestamp",
}

# ReAct 的决策轮上限是 Runtime 安全边界；模型输出只能提供受控估计，不能
# 直接扩大这个上限。后续按任务类型细化时仍需经过 resolve_step_budget。
DEFAULT_MAX_STEPS = 20
MIN_STEP_BUDGET = 1
MAX_STEP_BUDGET = DEFAULT_MAX_STEPS


@dataclass(frozen=True)
class StepBudget:
    """一次 Turn 的决策轮预算及其来源证据。"""

    default_steps: int
    estimated_steps: int | None
    safety_factor: float
    minimum_steps: int
    maximum_steps: int
    resolved_steps: int
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_steps": self.default_steps,
            "estimated_steps": self.estimated_steps,
            "safety_factor": self.safety_factor,
            "minimum_steps": self.minimum_steps,
            "maximum_steps": self.maximum_steps,
            "resolved_steps": self.resolved_steps,
            "source": self.source,
        }


def resolve_step_budget(
    *,
    default_steps: int = DEFAULT_MAX_STEPS,
    estimated_steps: int | None = None,
    safety_factor: float = 1.5,
    minimum_steps: int = MIN_STEP_BUDGET,
    maximum_steps: int = MAX_STEP_BUDGET,
) -> StepBudget:
    """解析受控决策轮预算，并保证估计值不能突破 Runtime 硬上限。"""
    if isinstance(default_steps, bool) or not isinstance(default_steps, int):
        raise ValueError("default_steps 必须是整数")
    if isinstance(estimated_steps, bool) or (
        estimated_steps is not None and not isinstance(estimated_steps, int)
    ):
        raise ValueError("estimated_steps 必须是整数或 None")
    if isinstance(minimum_steps, bool) or not isinstance(minimum_steps, int):
        raise ValueError("minimum_steps 必须是整数")
    if isinstance(maximum_steps, bool) or not isinstance(maximum_steps, int):
        raise ValueError("maximum_steps 必须是整数")
    if minimum_steps < MIN_STEP_BUDGET or maximum_steps < minimum_steps:
        raise ValueError("step budget 的 min/max 范围无效")
    if maximum_steps > MAX_STEP_BUDGET:
        raise ValueError("maximum_steps 不能突破 Runtime 硬上限")
    if default_steps < minimum_steps or default_steps > maximum_steps:
        raise ValueError("default_steps 必须位于 step budget 范围内")
    if estimated_steps is not None and estimated_steps < 1:
        raise ValueError("estimated_steps 必须大于 0")
    if safety_factor <= 0 or not math.isfinite(safety_factor):
        raise ValueError("safety_factor 必须是正数")

    if estimated_steps is None:
        resolved_steps = default_steps
        source = "runtime_default"
    else:
        resolved_steps = min(
            maximum_steps,
            max(minimum_steps, math.ceil(estimated_steps * safety_factor)),
        )
        source = "controlled_estimate"
    return StepBudget(
        default_steps=default_steps,
        estimated_steps=estimated_steps,
        safety_factor=safety_factor,
        minimum_steps=minimum_steps,
        maximum_steps=maximum_steps,
        resolved_steps=resolved_steps,
        source=source,
    )


@dataclass
class ProgressDelta:
    """一次工具观察相对历史观察的进度判定。"""

    status: str
    reason: str
    observation_fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "reason": self.reason,
            "observation_fingerprint": self.observation_fingerprint,
        }


@dataclass
class ProgressLedger:
    """记录动作、映射和观察结果；每个 Turn 创建一个实例。"""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        skill: str,
        args: dict[str, Any],
        *,
        agent_tool_name: str = "",
        business_tool_name: str = "",
        operation: str = "",
        capability_group: str = "",
        data_scope: str = "",
        freshness_requirement: str = "",
        tool_call_id: str = "",
        step_index: int | None = None,
    ) -> int:
        """记录动作及其跨系统映射，返回该动作的累计次数。"""
        call: dict[str, Any] = {"skill": skill, "args": dict(args)}
        metadata = {
            "agent_tool_name": agent_tool_name,
            "business_tool_name": business_tool_name,
            "operation": operation,
            "capability_group": capability_group,
            "data_scope": data_scope,
            "freshness_requirement": freshness_requirement,
            "tool_call_id": tool_call_id,
            "step_index": step_index,
        }
        call.update(
            {key: value for key, value in metadata.items() if value not in ("", None)}
        )
        self.calls.append(call)
        key = (skill, _args_key(args))
        return sum(1 for c in self.calls if (c["skill"], _args_key(c["args"])) == key)

    def reset(self) -> None:
        self.calls.clear()

    def total(self) -> int:
        return len(self.calls)

    def record_observation(
        self, skill: str, args: dict[str, Any], result: Any
    ) -> dict[str, str]:
        """挂载观察指纹并判定 advanced、unchanged 或 blocked。"""
        key = (skill, _args_key(args))
        for call in reversed(self.calls):
            if (call["skill"], _args_key(call["args"])) == key:
                fingerprint = observation_fingerprint(result)
                previous = [
                    item.get("observation_fingerprint")
                    for item in self.calls
                    if (item["skill"], _args_key(item["args"])) == key
                    and item.get("observation_fingerprint")
                    and item is not call
                ]
                result_data = result if isinstance(result, dict) else {}
                if result_data.get("error") and not result_data.get("retryable", False):
                    delta = ProgressDelta("blocked", "non_retryable_error", fingerprint)
                elif previous and previous[-1] == fingerprint:
                    delta = ProgressDelta("unchanged", "same_observation", fingerprint)
                else:
                    delta = ProgressDelta("advanced", "new_observation", fingerprint)
                call["observation_fingerprint"] = fingerprint
                call["progress"] = delta.status
                call["progress_reason"] = delta.reason
                return delta.to_dict()
        return ProgressDelta(
            "blocked", "observation_without_action", observation_fingerprint(result)
        ).to_dict()

    def last_action(self) -> dict[str, Any] | None:
        """返回最近一次动作，供受控终止持久化恢复门。"""
        return dict(self.calls[-1]) if self.calls else None

    def unchanged_count(self, skill: str, args: dict[str, Any]) -> int:
        """返回该动作连续得到 unchanged Observation 的次数。"""
        key = (skill, _args_key(args))
        count = 0
        for call in reversed(self.calls):
            if (call["skill"], _args_key(call["args"])) != key:
                break
            if call.get("progress") != "unchanged":
                break
            count += 1
        return count


# 兼容现有 Runtime 和外部测试调用方；新代码使用 ProgressLedger 语义。
CallTracker = ProgressLedger


def is_blocked_action(
    task_state: dict[str, Any] | None,
    skill: str,
    args: dict[str, Any],
) -> bool:
    """判断跨 Turn 恢复是否仍在重复被阻断的相同动作。"""
    if (
        not isinstance(task_state, dict)
        or task_state.get("resume_policy") != "ask_user"
    ):
        return False
    blocked = task_state.get("blocked_action")
    if not isinstance(blocked, dict):
        return False
    return blocked.get("agent_tool_name") == skill and _args_key(
        blocked.get("arguments", {})
    ) == _args_key(args)


def check_duplication(
    tracker: CallTracker,
    skill: str,
    args: dict[str, Any],
    threshold: int = 2,
) -> str | None:
    """重复 >= threshold 次返回警告消息，否则 None。"""
    count = sum(
        1
        for c in tracker.calls
        if c["skill"] == skill and _args_key(c["args"]) == _args_key(args)
    )
    if count >= threshold:
        return (
            f"重复调用：{skill} 已用相同参数调用 {count} 次。"
            "确认这是必要的；如非必要，请改用已有结果。"
        )
    return None


# ─── Doom Loop 检测 ────────────────────────────────────────────


def detect_doom_loop(call_history: list[dict[str, Any]]) -> str | None:
    """检测最近的调用是否构成死循环。

    call_history 元素：{"skill": str, "args": dict}
    返回注入给 LLM 的 reconsider 提示；无问题返回 None。
    """
    if len(call_history) < DUPLICATE_THRESHOLD:
        return None

    recent = call_history[-DOOM_LOOP_WINDOW:]

    # 检测：同一有效调用重复且没有产生新结果。
    counts: dict[tuple, int] = {}
    for c in recent:
        k = (c.get("skill", ""), _args_key(c.get("args", {})))
        counts[k] = counts.get(k, 0) + 1
        if counts[k] >= DUPLICATE_THRESHOLD:
            fingerprints = [
                str(item.get("observation_fingerprint"))
                for item in recent
                if (
                    item.get("skill", ""),
                    _args_key(item.get("args", {})),
                )
                == k
                and item.get("observation_fingerprint")
            ]
            if fingerprints and len(set(fingerprints)) > 1:
                continue
            return (
                f"检测到死循环：{c['skill']}({_truncate(c.get('args', {}))}) "
                f"已重复 {counts[k]} 次且没有产生新结果，已停止本轮执行。"
            )

    return None


# ─── 完成前 checklist ─────────────────────────────────────────


def pre_completion_checklist(
    plan: Any | None,
    tracker: CallTracker,
) -> list[str]:
    """final_answer 前检查。返回问题列表（空 = 通过）。

    - 如果有 plan：所有 step 必须 status='done' 或 'failed'
    - 重复调用 >=3 次的 skill 给 warning（不阻塞，只提示）
    """
    issues: list[str] = []

    if plan is not None:
        for i, step in enumerate(getattr(plan, "steps", [])):
            status = getattr(step, "status", "pending")
            if status not in ("done", "failed"):
                issues.append(
                    f"plan 步骤 {i + 1} {step.skill} 未完成（status={status}）"
                )

    # 重复调用 warning（不阻塞，只提示）
    seen: dict[tuple, int] = {}
    for c in tracker.calls:
        k = (c["skill"], _args_key(c["args"]))
        seen[k] = seen.get(k, 0) + 1
    for (skill, _), n in seen.items():
        if n >= 3:
            issues.append(f"警告：{skill} 已重复调用 {n} 次（可能是低效）")

    return issues


# ─── 辅助函数 ─────────────────────────────────────────────────


def _args_key(args: dict[str, Any]) -> str:
    """对有效参数做稳定序列化，避免字典顺序导致重复检测失效。"""
    if not isinstance(args, dict):
        return "n/a"
    return json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)


def observation_fingerprint(result: Any) -> str:
    """计算业务结果指纹，排除请求级易变字段。"""
    normalized = _without_volatile_keys(result)
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _without_volatile_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_volatile_keys(item)
            for key, item in value.items()
            if key not in _VOLATILE_RESULT_KEYS
        }
    if isinstance(value, list):
        return [_without_volatile_keys(item) for item in value]
    return value


def _truncate(args: dict[str, Any], max_len: int = 60) -> str:
    if not args:
        return "无参数"
    s = str(args)
    return s if len(s) <= max_len else s[:max_len] + "..."
