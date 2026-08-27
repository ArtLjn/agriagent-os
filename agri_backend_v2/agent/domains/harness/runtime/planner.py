"""任务规划器：把复杂请求拆成多步 plan。

跟 ReAct 的关系（参考 _example/core/planner.py）：
- ReAct：边想边做，每步 LLM 决策一次。适合简单请求。
- Planner：LLM 一次性规划多步，引擎按 plan 顺序执行。
  适合"查天气并创建日志"、"分别查询 A 和 B"这类需要多 skill 协同的任务。

集成方式：
- LLM 通过 function calling 调用 `make_plan` 工具触发规划
- react.py 识别 make_plan 工具名后转入 planner 处理
- 执行引擎复用 react._execute_single_skill，保持 HITL/trace 一致性
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_BUDGET_ESTIMATE_TOOL_NAME = "estimate_step_budget"
_BUDGET_ESTIMATE_SYSTEM_PROMPT = """你是 Agent Harness 的 Runtime 预算估算器。
你只负责估算完成用户请求所需的 ReAct 决策轮数，不执行任何业务工具，不回答用户。
请调用 estimate_step_budget，返回 estimated_steps 和 0 到 1 之间的 confidence。
estimated_steps 只计算正式 Agent 决策轮，不包含本次预算估算调用；宁可保守估算，也不要把安全系数自行算进去。"""


@dataclass
class Step:
    """Plan 中的一步。"""

    description: str
    skill: str
    args: dict[str, Any]
    status: str = "pending"  # pending | running | done | failed
    result: Any = None
    error: str | None = None


@dataclass
class Plan:
    """多步任务计划。"""

    goal: str
    steps: list[Step] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def all_done(self) -> bool:
        return all(s.status in ("done", "failed") for s in self.steps)

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.steps if s.status in ("done", "failed"))


def parse_plan(
    tool_args: dict[str, Any],
    user_input: str,
    valid_skills: dict[str, Any],
) -> Plan | None:
    """从 LLM 的 make_plan 工具参数解析 Plan。

    tool_args schema：
      {
        "goal": "目标描述",
        "steps": [
          {"description": "...", "skill": "...", "args": {...}}
        ]
      }

    valid_skills: react.py 传入的 skill_index（{name: Skill}），用于过滤未知 skill。
    <2 个有效步骤返回 None（让 ReAct 单步处理）。
    """
    raw_steps = tool_args.get("steps") or tool_args.get("plan") or []
    if not isinstance(raw_steps, list):
        return None

    steps: list[Step] = []
    for s in raw_steps:
        if not isinstance(s, dict) or "skill" not in s:
            continue
        skill_name = s["skill"]
        if skill_name not in valid_skills:
            logger.warning("[planner] 跳过未知 skill: %s", skill_name)
            continue
        steps.append(
            Step(
                description=str(s.get("description", "")).strip()
                or f"调用 {skill_name}",
                skill=skill_name,
                args=s.get("args") or {},
            )
        )

    if len(steps) < 2:
        logger.info("[planner] 有效步骤 <2, 退化为单步 ReAct: %d steps", len(steps))
        return None

    return Plan(
        goal=str(tool_args.get("goal") or user_input),
        steps=steps,
    )


def validate_plan(plan: Plan, skill_index: dict[str, Any]) -> list[str]:
    """校验 plan 中每步的必填参数是否齐全。返回 issues 列表（空 = 通过）。"""
    issues: list[str] = []
    for i, step in enumerate(plan.steps):
        skill = skill_index.get(step.skill)
        if skill is None:
            issues.append(f"步骤{i + 1} 未知 skill: {step.skill}")
            continue
        missing = skill.missing_required_params(step.args)
        if missing:
            issues.append(f"步骤{i + 1} {step.skill} 缺参数 {missing}")
    return issues


def plan_to_event_data(plan: Plan) -> dict[str, Any]:
    """转成 plan SSE 事件 data。"""
    return {
        "goal": plan.goal,
        "step_count": len(plan.steps),
        "steps": [
            {
                "description": s.description,
                "skill": s.skill,
                "args": s.args,
                "status": s.status,
            }
            for s in plan.steps
        ],
    }


def plan_summary_for_observation(plan: Plan) -> str:
    """plan 执行完后给 LLM 的 observation 文本。"""
    parts: list[str] = []
    for i, step in enumerate(plan.steps):
        if step.status == "failed":
            parts.append(f"步骤{i + 1} {step.skill} 失败: {step.error or '未知错误'}")
        elif step.status == "done":
            # 截断过长的 result
            r = step.result
            if isinstance(r, str):
                r_preview = r if len(r) <= 200 else r[:200] + "..."
            else:
                import json

                r_str = json.dumps(r, ensure_ascii=False, default=str)
                r_preview = r_str if len(r_str) <= 200 else r_str[:200] + "..."
            parts.append(f"步骤{i + 1} {step.skill} 成功: {r_preview}")
        else:
            parts.append(f"步骤{i + 1} {step.skill} 状态={step.status}")
    return f"[PLAN 完成 goal={plan.goal}] " + "；".join(parts)


def budget_estimate_messages(user_input: str) -> list[dict[str, str]]:
    """构造预算预估请求，隔离用户内容与 Runtime 控制规则。"""
    return [
        {"role": "system", "content": _BUDGET_ESTIMATE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {"user_request": str(user_input or "")[:4000]},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]


def parse_budget_estimate(
    tool_calls: list[dict[str, Any]], content: str = ""
) -> tuple[int, float] | None:
    """解析模型预算输出；非法或缺字段时交由 Runtime 使用 fallback。"""
    payload: dict[str, Any] | None = None
    for call in tool_calls:
        if call.get("name") != _BUDGET_ESTIMATE_TOOL_NAME:
            continue
        arguments = call.get("arguments")
        if isinstance(arguments, dict):
            payload = arguments
            break

    if payload is None and content:
        try:
            decoded = json.loads(content.strip())
        except (TypeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, dict):
            payload = decoded

    if payload is None:
        return None
    estimated_steps = payload.get("estimated_steps")
    confidence = payload.get("confidence")
    if isinstance(estimated_steps, bool) or not isinstance(estimated_steps, int):
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    if estimated_steps < 1 or not 0.0 <= confidence <= 1.0:
        return None
    return estimated_steps, float(confidence)


# make_plan 工具的 OpenAI schema（注入到 tools 列表）
MAKE_PLAN_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "make_plan",
        "description": (
            "一次性规划多步任务（2-5 步），引擎会按顺序执行每个步骤。"
            "适用于需要多 skill 协同的复杂任务，如『查询天气并创建对应农事日志』、"
            "『分别查询 A 农场和 B 农场状态』。"
            "不要用于简单单步任务（直接调用对应 skill 即可）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "本次规划的整体目标，简短一句话",
                },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "这一步要做什么",
                            },
                            "skill": {
                                "type": "string",
                                "description": "调用的 skill 名",
                            },
                            "args": {
                                "type": "object",
                                "description": "传给 skill 的参数",
                            },
                        },
                        "required": ["skill", "args"],
                    },
                    "minItems": 2,
                    "description": "按执行顺序排列的步骤列表",
                },
            },
            "required": ["goal", "steps"],
        },
    },
}


# 预算预估是 Runtime 内部调用，不加入业务 Skill Registry 的公开工具目录。
BUDGET_ESTIMATE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": _BUDGET_ESTIMATE_TOOL_NAME,
        "description": "估算完成用户请求所需的正式 ReAct 决策轮数。",
        "parameters": {
            "type": "object",
            "properties": {
                "estimated_steps": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "完成请求所需的正式 Agent 决策轮数，不包含预算估算调用",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "对本次轮数估算的置信度，范围 0 到 1",
                },
            },
            "required": ["estimated_steps", "confidence"],
        },
    },
}
