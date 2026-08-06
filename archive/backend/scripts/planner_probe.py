"""Planner Probe — 隔离评测 LLM 任务拆解能力。

模拟主链路 input → LLM 这一段,让 LLM 直接输出 PlanIR,
不进 ReAct 循环、不调真工具、不写库,只看 LLM 拆解能力。

probe 本身是纯执行器,测试用例从外部 YAML 文件加载。

用法:
    poetry run python -m scripts.planner_probe
    poetry run python -m scripts.planner_probe --cases path/to/cases.yaml
    poetry run python -m scripts.planner_probe --json report.json --report report.md
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.task_graph.capabilities.catalog import CAPABILITY_CATALOG
from app.agent.task_graph.compiler import compile_plan_ir
from app.agent.task_graph.models import PlanIR, PlanIRStep
from app.agent.task_graph.plan_ir import (
    PlanIRValidationError,
    validate_plan_ir,
)
from app.shared.llm import get_llm

logger = logging.getLogger("planner_probe")

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "planner_probe_cases.yaml"
PROBE_VERSION = "planner_probe_v0"


class LLMPlanStep(BaseModel):
    """LLM 输出的单步,字段对 LLM 友好,probe 负责转 PlanIRStep。"""

    id: str = Field(description="唯一标识, 如 step_1")
    action_type: str = Field(
        description="操作类型: query/calculate/synthesize/branch/parallel/approval/wait/merge"
    )
    capability: str | None = Field(
        default=None,
        description="catalog 中的 CapabilityDefinition.name, 如 QueryCropTemplate",
    )
    depends_on: list[str] = Field(
        default_factory=list, description="依赖的前置 step id 列表"
    )
    side_effect: str = Field(
        default="none", description="none(无副作用) / pending_only(只生成 pending 计划)"
    )
    description: str = Field(default="", description="一句话说明本步做什么")


class LLMPlanOutput(BaseModel):
    """LLM 输出的简化 PlanIR,probe 把它包成完整 PlanIR 再校验。"""

    task_type: str = Field(
        description="任务类型: planting_plan / crop_cycle_setup / cost_analysis 等"
    )
    intent: str = Field(description="一句话业务意图")
    steps: list[LLMPlanStep] = Field(description="拆解出的步骤列表")


SYSTEM_PROMPT = """你是 farm-manager 农场的任务规划器。

职责: 把用户的业务意图拆解成可执行的步骤列表。
禁止: 直接回答用户、调用工具、做业务计算。

# 可用 Capability Catalog
{catalog}

# TaskType 枚举(选一个)
planting_plan / crop_cycle_setup / field_work_assignment /
inventory_management / cost_analysis / pest_diagnosis /
retry_or_resume / legacy_skill_fallback

# action_type 枚举(每个 step 选一个)
query(查询) / calculate(计算) / synthesize(综合) /
branch(分支) / parallel(并行) / approval(写操作必须经) /
wait(等待) / merge(合并)

# side_effect 枚举
none(默认,无副作用) / pending_only(写操作必须用这个)
s
# 拆解原则
1. 每个 step 的 capability 必须在 catalog 中(纯读查询也要对应 capability)
2. 写操作 step 的 side_effect 必须是 pending_only,且后续必须有一个 approval step
3. depends_on 字段引用前置 step 的 id
4. 信息不全时,只生成一个 synthesize step,不编造查询
5. step.id 用 step_1, step_2, ... 这种简单序号

# 输出示例
用户输入"帮我规划秋季草莓 20 亩":
{{
  "task_type": "planting_plan",
  "intent": "规划秋季草莓种植 20 亩",
  "steps": [
    {{"id": "step_1", "action_type": "query", "capability": "QueryCropTemplate", "depends_on": [], "side_effect": "none", "description": "查草莓模板"}},
    {{"id": "step_2", "action_type": "calculate", "capability": "CalculatePlantingLayout", "depends_on": ["step_1"], "side_effect": "none", "description": "算种植布局"}},
    {{"id": "step_3", "action_type": "synthesize", "capability": "SynthesizePlantingPlan", "depends_on": ["step_2"], "side_effect": "none", "description": "综合方案"}},
    {{"id": "step_4", "action_type": "approval", "capability": "ProposeCreateCyclePlan", "depends_on": ["step_3"], "side_effect": "pending_only", "description": "提交待确认的茬口创建计划"}}
  ]
}}

严格按 schema 输出,不要额外字段,不要解释。
"""


@dataclass(frozen=True)
class ProbeCase:
    name: str
    user_input: str
    expect_task_type: str
    expect_capabilities: list[str]
    note: str = ""


@dataclass
class CaseResult:
    case: ProbeCase
    plan_ir: PlanIR | None = None
    validation_issues: list[dict[str, Any]] = field(default_factory=list)
    compile_error: str | None = None
    latency_ms: int = 0
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.case.name,
            "user_input": self.case.user_input,
            "expect_task_type": self.case.expect_task_type,
            "expect_capabilities": self.case.expect_capabilities,
            "note": self.case.note,
            "task_type": self.plan_ir.task_type if self.plan_ir else None,
            "steps": (
                [self._step_payload(s) for s in self.plan_ir.steps]
                if self.plan_ir
                else []
            ),
            "actual_capabilities": (
                [s.capability for s in self.plan_ir.steps if s.capability]
                if self.plan_ir
                else []
            ),
            "validation_issues": self.validation_issues,
            "compile_error": self.compile_error,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }

    @staticmethod
    def _step_payload(s: PlanIRStep) -> dict[str, Any]:
        return {
            "step_id": s.step_id,
            "op": s.op,
            "capability": s.capability,
            "side_effect": s.side_effect,
            "needs": s.needs,
        }


def load_cases(path: Path) -> list[ProbeCase]:
    """从 YAML 文件加载测试用例。"""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases_data = raw.get("cases", []) if isinstance(raw, dict) else []
    return [
        ProbeCase(
            name=c["name"],
            user_input=c["user_input"],
            expect_task_type=c["expect_task_type"],
            expect_capabilities=c.get("expect_capabilities", []),
            note=c.get("note", ""),
        )
        for c in cases_data
    ]


def _format_catalog() -> str:
    lines = []
    for name, cap in CAPABILITY_CATALOG.items():
        lines.append(
            f"- {name}: {cap.description} "
            f"(input={cap.contract.input_types}, "
            f"output={cap.contract.output_type}, "
            f"side_effect={cap.side_effect})"
        )
    return "\n".join(lines)


def _wrap_to_plan_ir(case: ProbeCase, llm_output: LLMPlanOutput) -> PlanIR:
    """把 LLM 输出包成完整 PlanIR,probe 自填元数据字段。"""
    context_hash = hashlib.sha1(
        f"{case.name}:{case.user_input}:{llm_output.task_type}".encode("utf-8")
    ).hexdigest()[:16]
    return PlanIR(
        ir_id=f"probe_{case.name}",
        task_type=llm_output.task_type,  # type: ignore[arg-type]
        intent=llm_output.intent,
        planner_version=PROBE_VERSION,
        context_hash=context_hash,
        response_contract="ProbeResult",
        steps=[
            PlanIRStep(
                step_id=s.id,
                op=s.action_type,  # type: ignore[arg-type]
                capability=s.capability,
                needs=s.depends_on,
                side_effect=s.side_effect,  # type: ignore[arg-type]
            )
            for s in llm_output.steps
        ],
    )


async def _probe_one(case: ProbeCase) -> CaseResult:
    result = CaseResult(case=case)
    llm = get_llm(role="generation")
    structured_llm = llm.with_structured_output(LLMPlanOutput)
    system = SystemMessage(content=SYSTEM_PROMPT.format(catalog=_format_catalog()))
    human = HumanMessage(content=case.user_input)

    start = time.perf_counter()
    try:
        llm_output = await structured_llm.ainvoke([system, human])
        result.plan_ir = _wrap_to_plan_ir(case, llm_output)
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
    result.latency_ms = int((time.perf_counter() - start) * 1000)
    if result.error or result.plan_ir is None:
        return result

    try:
        issues = validate_plan_ir(result.plan_ir)
        result.validation_issues = issues
        if not issues:
            compile_plan_ir(result.plan_ir)
    except PlanIRValidationError as exc:
        result.compile_error = ", ".join(exc.codes)
    except Exception as exc:  # noqa: BLE001
        result.compile_error = f"{type(exc).__name__}: {exc}"
    return result


async def _run_all(cases: list[ProbeCase]) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        print(f"── 跑 case: {case.name} ──", flush=True)
        result = await _probe_one(case)
        results.append(result)
        _print_inline(result)
    return results


def _print_inline(result: CaseResult) -> None:
    if result.error:
        print(f"  ❌ LLM 调用失败: {result.error[:120]}", flush=True)
        return
    if result.validation_issues:
        codes = [i.get("code") for i in result.validation_issues]
        print(f"  ⚠️  校验失败: {codes}", flush=True)
        return
    if result.compile_error:
        print(f"  ⚠️  编译失败: {result.compile_error}", flush=True)
        return
    caps = [s.capability for s in result.plan_ir.steps if s.capability]
    print(
        f"  ✅ task={result.plan_ir.task_type} steps={len(result.plan_ir.steps)} "
        f"caps={caps} latency={result.latency_ms}ms",
        flush=True,
    )


def _capability_hit_rate(results: list[CaseResult]) -> float:
    hit, total = 0, 0
    for r in results:
        if not r.plan_ir or r.error:
            continue
        actual = {s.capability for s in r.plan_ir.steps if s.capability}
        for expected in r.case.expect_capabilities:
            total += 1
            if expected in actual:
                hit += 1
    return hit / total if total else 0.0


def _render_report(results: list[CaseResult]) -> str:
    total = len(results)
    ok = sum(
        1
        for r in results
        if r.error is None and not r.validation_issues and r.compile_error is None
    )
    task_match = sum(
        1
        for r in results
        if r.plan_ir and r.plan_ir.task_type == r.case.expect_task_type
    )
    cap_hit_rate = _capability_hit_rate(results)

    lines = [
        "# Planner Probe 报告",
        "",
        "## 总览",
        f"- 用例数: {total}",
        f"- 通过 4 层校验: {ok}/{total}",
        f"- task_type 命中: {task_match}/{total}",
        f"- 期望 capability 命中率: {cap_hit_rate:.1%}",
        "",
        "## 用例明细",
    ]
    for r in results:
        lines.extend(_render_case(r))
        lines.append("")
    return "\n".join(lines)


def _render_case(r: CaseResult) -> list[str]:
    lines = [f"### {r.case.name}", ""]
    lines.append(f"- **输入**: `{r.case.user_input}`")
    lines.append(f"- **期望 task_type**: `{r.case.expect_task_type}`")
    lines.append(f"- **备注**: {r.case.note}")
    if r.error:
        lines.append(f"- ❌ **LLM 调用失败**: `{r.error}`")
        return lines
    lines.append(f"- **实际 task_type**: `{r.plan_ir.task_type}`")
    lines.append(f"- **延迟**: {r.latency_ms} ms")
    if r.validation_issues:
        codes = [i.get("code") for i in r.validation_issues]
        lines.append(f"- ⚠️ **静态校验失败**: `{codes}`")
        return lines
    if r.compile_error:
        lines.append(f"- ⚠️ **编译失败**: `{r.compile_error}`")
        return lines
    lines.append("- **step 列表**:")
    for s in r.plan_ir.steps:
        cap_str = f" cap={s.capability}" if s.capability else ""
        needs = f" needs={s.needs}" if s.needs else ""
        lines.append(
            f"  - `{s.step_id}` op=`{s.op}`{cap_str} side=`{s.side_effect}`{needs}"
        )
    actual = {s.capability for s in r.plan_ir.steps if s.capability}
    missing = set(r.case.expect_capabilities) - actual
    extra = actual - set(r.case.expect_capabilities)
    if missing:
        lines.append(f"- 🔍 **缺 capability**: `{sorted(missing)}`")
    if extra:
        lines.append(f"- ➕ **额外 capability**: `{sorted(extra)}`")
    return lines


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Planner Probe — LLM 任务拆解评测")
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help=f"测试用例 YAML 路径, 默认: {DEFAULT_CASES_PATH.name}",
    )
    parser.add_argument("--json", dest="json_path", help="JSON 报告输出路径")
    parser.add_argument("--report", help="Markdown 报告输出路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    if not args.cases.exists():
        raise SystemExit(f"cases 文件不存在: {args.cases}")

    cases = load_cases(args.cases)
    if not cases:
        raise SystemExit(f"cases 文件为空: {args.cases}")

    results = asyncio.run(_run_all(cases))
    report = _render_report(results)
    print("\n" + report)

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(
                [r.to_payload() for r in results],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nJSON 报告已写入: {args.json_path}")
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"Markdown 报告已写入: {args.report}")

    has_failure = any(
        r.error or r.validation_issues or r.compile_error for r in results
    )
    if has_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
