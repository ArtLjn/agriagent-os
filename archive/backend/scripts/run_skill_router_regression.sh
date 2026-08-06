#!/usr/bin/env bash
# Skill Router 批量回归测试。
#
# 默认跑离线确定性用例和向量噪声用例，不依赖 QuillRAG 网络服务。
# 需要验证真实线上向量库时设置 RUN_LIVE_VECTOR=1。
#
# 用法:
#   bash backend/scripts/run_skill_router_regression.sh
#   RUN_LIVE_VECTOR=1 bash backend/scripts/run_skill_router_regression.sh
#   RUN_PYTEST=0 PYTHON_BIN=/path/to/python bash backend/scripts/run_skill_router_regression.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYENV_PYTHON="/Users/ljn/.pyenv/versions/3.11.5/bin/python"
PYTHON_BIN="${PYTHON_BIN:-}"
RUN_PYTEST="${RUN_PYTEST:-1}"
RUN_LIVE_VECTOR="${RUN_LIVE_VECTOR:-0}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$PYENV_PYTHON" ]]; then
    PYTHON_BIN="$PYENV_PYTHON"
  else
    PYTHON_BIN="python3"
  fi
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"
export RUN_LIVE_VECTOR

cd "$BACKEND_DIR"

echo "============================================================"
echo " Skill Router Regression"
echo " backend        : $BACKEND_DIR"
echo " python         : $PYTHON_BIN"
echo " run_pytest     : $RUN_PYTEST"
echo " run_live_vector: $RUN_LIVE_VECTOR"
echo "============================================================"

if [[ "$RUN_PYTEST" == "1" ]]; then
  "$PYTHON_BIN" -m pytest -q -p no:cacheprovider \
    tests/agent/router/test_skill_router.py::test_public_recent_what_doing_selects_enabled_search_tool \
    tests/agent/router/test_skill_router.py::test_public_recent_what_doing_keeps_search_rule_over_vector_noise \
    tests/agent/router/test_skill_router.py::test_public_recent_activity_selects_enabled_search_tool \
    tests/agent/router/test_skill_router.py::test_public_recent_activity_keeps_search_rule_over_vector_noise \
    tests/agent/router/test_hybrid_operation_retriever.py::test_hybrid_retriever_drops_candidates_that_only_match_generic_terms \
    --tb=short
fi

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Callable

from app.agent.router.hybrid_retriever import HybridOperationRetriever
from app.agent.router.service import SkillRouter


@dataclass(frozen=True)
class ToolStub:
    name: str
    description: str = ""


@dataclass(frozen=True)
class RouteCase:
    case_id: str
    message: str
    tools: tuple[str, ...]
    expected_tools: tuple[str, ...] | None = None
    expected_operations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    forbidden_tools: tuple[str, ...] = ()
    noise_skill: str | None = None
    live_vector: bool = False


CORE_READ_TOOLS = (
    "web_search",
    "get_farm_status",
    "manage_farm_logs",
    "manage_cost",
    "manage_crop_cycle",
    "manage_work_orders",
    "manage_workers",
    "manage_labor_payment",
    "manage_planting_units",
    "weather",
)

CASES = (
    RouteCase(
        case_id="external.trump_recent_what_doing",
        message="特朗普最近在干嘛",
        tools=CORE_READ_TOOLS,
        expected_tools=("web_search",),
        expected_operations={"web_search": ("search",)},
        noise_skill="manage_farm_logs",
        live_vector=True,
    ),
    RouteCase(
        case_id="external.trump_recent_activity",
        message="最近特朗普有啥活动",
        tools=CORE_READ_TOOLS,
        expected_tools=("web_search",),
        expected_operations={"web_search": ("search",)},
        noise_skill="get_farm_status",
        live_vector=True,
    ),
    RouteCase(
        case_id="external.trump_latest_activity",
        message="特朗普最新活动",
        tools=CORE_READ_TOOLS,
        expected_tools=("web_search",),
        expected_operations={"web_search": ("search",)},
        noise_skill="manage_crop_cycle",
        live_vector=True,
    ),
    RouteCase(
        case_id="internal.farm_recent_guard",
        message="农场最近在干嘛",
        tools=CORE_READ_TOOLS,
        forbidden_tools=("web_search",),
        noise_skill="web_search",
        live_vector=True,
    ),
    RouteCase(
        case_id="internal.worker_recent_guard",
        message="这个工人最近在干嘛",
        tools=CORE_READ_TOOLS,
        forbidden_tools=("web_search",),
        noise_skill="web_search",
        live_vector=True,
    ),
    RouteCase(
        case_id="business.cost_summary",
        message="这个月花了多少钱",
        tools=CORE_READ_TOOLS,
        expected_tools=("manage_cost",),
        expected_operations={"manage_cost": ("query_summary",)},
    ),
    RouteCase(
        case_id="business.cost_debt",
        message="我有哪些欠款",
        tools=CORE_READ_TOOLS,
        expected_tools=("manage_cost",),
        expected_operations={"manage_cost": ("query_debt",)},
    ),
    RouteCase(
        case_id="business.labor_payable",
        message="还欠多少人工钱",
        tools=CORE_READ_TOOLS,
        expected_tools=("manage_labor_payment",),
        expected_operations={"manage_labor_payment": ("query_payables",)},
    ),
    RouteCase(
        case_id="business.crop_cycles",
        message="我的茬口有哪些",
        tools=CORE_READ_TOOLS,
        expected_tools=("manage_crop_cycle",),
        expected_operations={"manage_crop_cycle": ("query_cycles",)},
    ),
    RouteCase(
        case_id="business.planting_units",
        message="查一下我有哪些种植单元",
        tools=CORE_READ_TOOLS,
        expected_tools=("manage_planting_units",),
        expected_operations={"manage_planting_units": ("query_units",)},
    ),
)


def build_tools(names: tuple[str, ...]) -> list[ToolStub]:
    return [ToolStub(name=name, description=name) for name in names]


def make_router(vector_search: Callable | None) -> SkillRouter:
    router = SkillRouter()
    router._hybrid_retriever = HybridOperationRetriever(vector_search=vector_search)
    return router


def noise_vector_search(noise_skill: str) -> Callable:
    def _search(_query: str, candidates) -> dict[str, float]:
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.97 if candidate.name == noise_skill else 0.18
            )
            for candidate in candidates
        }

    return _search


def assert_case(case: RouteCase, mode: str, router: SkillRouter) -> str | None:
    decision = router.route(case.message, build_tools(case.tools))
    selected_tools = tuple(decision.selected_tools)
    selected_operations = {
        skill: tuple(operations)
        for skill, operations in decision.selected_operations.items()
    }
    failures: list[str] = []

    if case.expected_tools is not None and selected_tools != case.expected_tools:
        failures.append(
            f"expected_tools={case.expected_tools} actual={selected_tools}"
        )
    for tool_name in case.forbidden_tools:
        if tool_name in selected_tools:
            failures.append(f"forbidden_tool_selected={tool_name}")
    for capability, operations in case.expected_operations.items():
        actual = selected_operations.get(capability)
        if actual != operations:
            failures.append(
                f"expected_operations[{capability}]={operations} actual={actual}"
            )

    if not failures:
        print(
            f"PASS {mode:<12} {case.case_id:<36} "
            f"tools={list(selected_tools)} ops={selected_operations} "
            f"path={decision.evidence.get('selection_path')}"
        )
        return None

    top = decision.evidence.get("recall", {}).get("top_candidates")
    explanations = decision.evidence.get("candidate_explanations")
    return (
        f"FAIL {mode} {case.case_id}: {'; '.join(failures)}\n"
        f"  message: {case.message}\n"
        f"  selected_tools: {list(selected_tools)}\n"
        f"  selected_operations: {selected_operations}\n"
        f"  selection_path: {decision.evidence.get('selection_path')}\n"
        f"  recall_top_candidates: {top}\n"
        f"  candidate_explanations: {explanations}"
    )


def main() -> int:
    failures: list[str] = []
    run_live_vector = os.environ.get("RUN_LIVE_VECTOR") == "1"

    local_router = make_router(vector_search=None)
    for case in CASES:
        failure = assert_case(case, "local", local_router)
        if failure:
            failures.append(failure)

    for case in CASES:
        if case.noise_skill is None:
            continue
        router = make_router(vector_search=noise_vector_search(case.noise_skill))
        failure = assert_case(case, "vector_noise", router)
        if failure:
            failures.append(failure)

    if run_live_vector:
        live_router = SkillRouter()
        for case in CASES:
            if not case.live_vector:
                continue
            failure = assert_case(case, "live_vector", live_router)
            if failure:
                failures.append(failure)

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    print("============================================================")
    print("Skill Router 回归通过。")
    if not run_live_vector:
        print("提示: 设置 RUN_LIVE_VECTOR=1 可验证真实 QuillRAG 向量库抢路由风险。")
    print("============================================================")
    return 0


raise SystemExit(main())
PY
