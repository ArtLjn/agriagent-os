"""Verification 层：CallTracker + Doom Loop 检测 + 完成前 checklist。

参考：harness_study/_example/tools/verify.py + tools/safety.py

合并原因：safety.py 的 detect_doom_loop 和 verify.py 的 CallTracker
都是"防止 agent 重复犯错"的同一关注点，合并到单文件避免碎片化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ─── CallTracker ──────────────────────────────────────────────

# 滑动窗口大小（看最近 N 次调用判断是否死循环）
DOOM_LOOP_WINDOW = 5
# 同一 (skill, args) 出现 >= N 次视为死循环
DUPLICATE_THRESHOLD = 3
# 同一 skill（不同 args）出现 >= N 次也视为死循环
SAME_SKILL_THRESHOLD = 4


@dataclass
class CallTracker:
    """跟踪 (skill, args_key) 调用次数。每个 turn 重置一次。"""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, skill: str, args: dict[str, Any]) -> int:
        """记录一次调用，返回该 (skill, args) 的累计次数。"""
        self.calls.append({"skill": skill, "args": args})
        key = (skill, _args_key(args))
        return sum(
            1 for c in self.calls
            if (c["skill"], _args_key(c["args"])) == key
        )

    def reset(self) -> None:
        self.calls.clear()

    def total(self) -> int:
        return len(self.calls)


def check_duplication(
    tracker: CallTracker,
    skill: str,
    args: dict[str, Any],
    threshold: int = 2,
) -> str | None:
    """重复 >= threshold 次返回警告消息，否则 None。"""
    count = sum(
        1 for c in tracker.calls
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

    # 检测 1：同一 (skill, args_hash) 出现 >= 3 次
    counts: dict[tuple, int] = {}
    for c in recent:
        k = (c.get("skill", ""), _args_key(c.get("args", {})))
        counts[k] = counts.get(k, 0) + 1
        if counts[k] >= DUPLICATE_THRESHOLD:
            return (
                f"检测到死循环：{c['skill']}({_truncate(c.get('args', {}))}) "
                f"已重复 {counts[k]} 次。请改用不同 skill 或换参数；"
                "如确实无法继续，请直接 final_answer 向用户说明。"
            )

    # 检测 2：同一 skill（不同 args）出现 >= 4 次
    skill_counts: dict[str, int] = {}
    for c in recent:
        s = c.get("skill", "")
        skill_counts[s] = skill_counts.get(s, 0) + 1
        if skill_counts[s] >= SAME_SKILL_THRESHOLD:
            return (
                f"检测到死循环：{s} 在最近 {DOOM_LOOP_WINDOW} 次调用中出现 "
                f"{skill_counts[s]} 次（参数不同）。"
                "请考虑换一种策略，或直接 final_answer 向用户说明无法继续。"
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
                issues.append(f"plan 步骤 {i+1} {step.skill} 未完成（status={status}）")

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
    """对 args 取稳定 hash key（不用 hash() 因为跨进程不稳定）。"""
    if not isinstance(args, dict):
        return "n/a"
    items = sorted((str(k), str(v)) for k, v in args.items())
    return "|".join(f"{k}={v}" for k, v in items)


def _truncate(args: dict[str, Any], max_len: int = 60) -> str:
    if not args:
        return "无参数"
    s = str(args)
    return s if len(s) <= max_len else s[:max_len] + "..."
