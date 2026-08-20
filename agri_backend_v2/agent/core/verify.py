"""Verification 层：CallTracker + Doom Loop 检测 + 完成前 checklist。

参考：harness_study/_example/tools/verify.py + tools/safety.py

合并原因：safety.py 的 detect_doom_loop 和 verify.py 的 CallTracker
都是"防止 agent 重复犯错"的同一关注点，合并到单文件避免碎片化。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

# ─── CallTracker ──────────────────────────────────────────────

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


@dataclass
class CallTracker:
    """跟踪 (skill, args_key) 调用次数。每个 turn 重置一次。"""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, skill: str, args: dict[str, Any]) -> int:
        """记录一次调用，返回该 (skill, args) 的累计次数。"""
        self.calls.append({"skill": skill, "args": dict(args)})
        key = (skill, _args_key(args))
        return sum(1 for c in self.calls if (c["skill"], _args_key(c["args"])) == key)

    def reset(self) -> None:
        self.calls.clear()

    def total(self) -> int:
        return len(self.calls)

    def record_observation(self, skill: str, args: dict[str, Any], result: Any) -> None:
        """把结果指纹挂到最近一次调用，区分重复查询和数据已变化。"""
        key = (skill, _args_key(args))
        for call in reversed(self.calls):
            if (call["skill"], _args_key(call["args"])) == key:
                call["observation_fingerprint"] = observation_fingerprint(result)
                return


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
