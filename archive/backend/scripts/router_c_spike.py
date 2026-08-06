"""Router 方案 C Spike — 验证删除 web_search 规则路径的效果。

对照实验:
  Mode A (current_rule)   : 用现有 looks_like_web_search 规则判定 web_search 是否被允许
  Mode B (plan_c LLM 自选): bind 全部 read 工具给 LLM, 让 LLM 自选
  Mode C (bm25+vector)    : 调真实 HybridOperationRetriever, top1 即预测结果

输出每个 case 三种判定结果, 用于判断方案 C 是否真的更准, 以及跟纯算法召回的对比。

用法:
    .venv/bin/python -m scripts.router_c_spike
    .venv/bin/python -m scripts.router_c_spike --cases path/to/cases.yaml
    .venv/bin/python -m scripts.router_c_spike --json report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.router.catalog import SkillCatalog
from app.agent.router.classifier_signals import looks_like_web_search
from app.agent.router.hybrid_retriever import HybridOperationRetriever
from app.agent.router.skill_vector_store import build_skill_vector_search_fn
from app.infra.pending_actions import WRITE_SKILLS
from app.shared.llm import get_llm
from app.skills import get_langchain_tools

logger = logging.getLogger("router_c_spike")

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "router_c_spike_cases.yaml"

SYSTEM_PROMPT = """你是 farm-manager 农场助手。根据用户问题选择最合适的工具调用。

# 工具选择原则
1. 实时信息类问题(新闻、人物动态、价格、行情、政策、上市时间、热点事件) → web_search
2. 农场内部数据查询(茬口、作物、地块、账务、工人、作业单) → 对应内部工具
3. 天气查询 → weather
4. 不确定归属时, 优先判断信息来源是"外部实时"还是"内部数据库"

# 重要约束
- 一次只调一个工具
- 选 tool 时只考虑用户意图, 不考虑前几轮对话
- 不要因为问题里出现"农场"等词就回避 web_search, 只要主体意图是外部实时信息就选 web_search

# 可用工具 schema 已经 bind, 直接基于 schema 选择。
"""


@dataclass(frozen=True)
class ProbeCase:
    name: str
    user_input: str
    expect_tool: str
    note: str = ""


@dataclass
class CaseResult:
    case: ProbeCase
    rule_allows_web_search: bool = False
    llm_chosen_tools: list[str] = field(default_factory=list)
    llm_latency_ms: int = 0
    hybrid_top_tools: list[str] = field(default_factory=list)
    hybrid_latency_ms: int = 0
    hybrid_vector_used: bool = False
    error: str | None = None

    @property
    def llm_picks_web_search(self) -> bool:
        return "web_search" in self.llm_chosen_tools

    @property
    def rule_hits(self) -> bool:
        if self.case.expect_tool == "web_search":
            return self.rule_allows_web_search
        return not self.rule_allows_web_search

    @property
    def plan_c_hits(self) -> bool:
        if self.error:
            return False
        if self.case.expect_tool == "web_search":
            return self.llm_picks_web_search
        return self.case.expect_tool in self.llm_chosen_tools

    @property
    def hybrid_hits(self) -> bool:
        """Mode C: BM25+向量 top-K 是否包含 expect_tool。"""
        if not self.hybrid_top_tools:
            return False
        if self.case.expect_tool == "web_search":
            return "web_search" in self.hybrid_top_tools
        return self.case.expect_tool in self.hybrid_top_tools

    @property
    def latency_ms(self) -> int:
        return self.llm_latency_ms

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.case.name,
            "user_input": self.case.user_input,
            "expect_tool": self.case.expect_tool,
            "note": self.case.note,
            "rule_allows_web_search": self.rule_allows_web_search,
            "llm_chosen_tools": self.llm_chosen_tools,
            "llm_picks_web_search": self.llm_picks_web_search,
            "hybrid_top_tools": self.hybrid_top_tools,
            "hybrid_vector_used": self.hybrid_vector_used,
            "llm_latency_ms": self.llm_latency_ms,
            "hybrid_latency_ms": self.hybrid_latency_ms,
            "rule_hits": self.rule_hits,
            "plan_c_hits": self.plan_c_hits,
            "hybrid_hits": self.hybrid_hits,
            "error": self.error,
        }


def load_cases(path: Path) -> list[ProbeCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases_data = raw.get("cases", []) if isinstance(raw, dict) else []
    return [
        ProbeCase(
            name=c["name"],
            user_input=c["user_input"],
            expect_tool=c["expect_tool"],
            note=c.get("note", ""),
        )
        for c in cases_data
    ]


def _format_tool_list(tools: list) -> str:
    lines = []
    for t in tools:
        desc = (t.description or "").split("\n", 1)[0][:80]
        lines.append(f"- {t.name}: {desc}")
    return "\n".join(lines)


def _build_hybrid_retriever(
    all_tools: list,
) -> tuple[HybridOperationRetriever, SkillCatalog]:
    catalog = SkillCatalog.from_tools(all_tools)
    vector_search = build_skill_vector_search_fn()
    retriever = HybridOperationRetriever(vector_search=vector_search)
    return retriever, catalog


def _run_hybrid_top_k(
    retriever: HybridOperationRetriever,
    catalog: SkillCatalog,
    user_input: str,
    k: int = 3,
) -> tuple[list[str], int, bool]:
    """跑 BM25+向量混合召回, 返回 top-K 工具名 + 耗时 + 是否用到向量。"""
    candidates = catalog.candidates()
    start = time.perf_counter()
    result = retriever.retrieve(user_input, candidates, limit=k)
    latency_ms = int((time.perf_counter() - start) * 1000)
    recall = result.recall or {}
    vector_used = (
        bool(recall.get("vector_search_used")) or retriever.vector_index_enabled
    )
    return list(result.selected_names), latency_ms, vector_used


async def _probe_one(
    case: ProbeCase,
    all_tools: list,
    hybrid_retriever: HybridOperationRetriever,
    catalog: SkillCatalog,
) -> CaseResult:
    result = CaseResult(case=case)
    result.rule_allows_web_search = looks_like_web_search(case.user_input)

    hybrid_top, hybrid_lat, hybrid_vec = _run_hybrid_top_k(
        hybrid_retriever, catalog, case.user_input, k=3
    )
    result.hybrid_top_tools = hybrid_top
    result.hybrid_latency_ms = hybrid_lat
    result.hybrid_vector_used = hybrid_vec

    read_tools = [t for t in all_tools if t.name not in WRITE_SKILLS]
    system = SystemMessage(
        content=SYSTEM_PROMPT + "\n# 可用工具列表\n" + _format_tool_list(read_tools)
    )
    human = HumanMessage(content=case.user_input)

    start = time.perf_counter()
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            fresh_llm = get_llm(role="generation").bind_tools(read_tools)
            resp = await fresh_llm.ainvoke([system, human])
            result.llm_chosen_tools = [
                tc.get("name", "") for tc in (resp.tool_calls or [])
            ]
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < 2:
                await asyncio.sleep(1.0)
    if last_exc is not None:
        result.error = f"{type(last_exc).__name__}: {last_exc}"
    result.llm_latency_ms = int((time.perf_counter() - start) * 1000)
    return result


async def _run_all(cases: list[ProbeCase]) -> list[CaseResult]:
    all_tools = get_langchain_tools(farm_id=2)
    print(
        f"已加载 {len(all_tools)} 个工具, "
        f"{sum(1 for t in all_tools if t.name not in WRITE_SKILLS)} 个 read 工具暴露给 LLM"
    )
    hybrid_retriever, catalog = _build_hybrid_retriever(all_tools)
    vec_status = (
        "已启用" if hybrid_retriever.vector_index_enabled else "未启用 (仅 BM25+词法)"
    )
    print(f"HybridOperationRetriever 向量索引: {vec_status}")
    results: list[CaseResult] = []
    for case in cases:
        print(f"── 跑 case: {case.name} ──", flush=True)
        result = await _probe_one(case, all_tools, hybrid_retriever, catalog)
        results.append(result)
        _print_inline(result)
    return results


def _print_inline(r: CaseResult) -> None:
    if r.error:
        print(f"  ❌ LLM 调用失败: {r.error[:120]}", flush=True)
        return
    flag_rule = "✅" if r.rule_hits else "❌"
    flag_c = "✅" if r.plan_c_hits else "❌"
    flag_h = "✅" if r.hybrid_hits else "❌"
    print(
        f"  expect={r.case.expect_tool} | "
        f"rule {flag_rule} | "
        f"hybrid_top3={r.hybrid_top_tools} {flag_h} ({r.hybrid_latency_ms}ms) | "
        f"llm={r.llm_chosen_tools} {flag_c} ({r.llm_latency_ms}ms)",
        flush=True,
    )


def _render_report(results: list[CaseResult]) -> str:
    total = len(results)
    rule_pass = sum(1 for r in results if r.rule_hits)
    plan_c_pass = sum(1 for r in results if r.plan_c_hits)
    hybrid_pass = sum(1 for r in results if r.hybrid_hits)
    web_search_cases = [r for r in results if r.case.expect_tool == "web_search"]
    rule_web = sum(1 for r in web_search_cases if r.rule_hits)
    plan_c_web = sum(1 for r in web_search_cases if r.plan_c_hits)
    hybrid_web = sum(1 for r in web_search_cases if r.hybrid_hits)

    valid_llm_lat = [r.llm_latency_ms for r in results if not r.error]
    valid_hybrid_lat = [r.hybrid_latency_ms for r in results]
    avg_llm_lat = sum(valid_llm_lat) / len(valid_llm_lat) if valid_llm_lat else 0
    max_llm_lat = max(valid_llm_lat) if valid_llm_lat else 0
    min_llm_lat = min(valid_llm_lat) if valid_llm_lat else 0
    total_llm_lat = sum(valid_llm_lat)
    avg_hybrid_lat = (
        sum(valid_hybrid_lat) / len(valid_hybrid_lat) if valid_hybrid_lat else 0
    )
    max_hybrid_lat = max(valid_hybrid_lat) if valid_hybrid_lat else 0
    min_hybrid_lat = min(valid_hybrid_lat) if valid_hybrid_lat else 0
    total_hybrid_lat = sum(valid_hybrid_lat)
    vec_used_count = sum(1 for r in results if r.hybrid_vector_used)

    lines = [
        "# Router 方案 C Spike 报告",
        "",
        "## 总览",
        f"- 用例数: {total}",
        f"- Mode A (current_rule) 命中       : {rule_pass}/{total} = {rule_pass / total:.1%}",
        f"- Mode B (plan_c LLM 自选) 命中    : {plan_c_pass}/{total} = {plan_c_pass / total:.1%}",
        f"- Mode C (BM25+向量 top3) 命中     : {hybrid_pass}/{total} = {hybrid_pass / total:.1%}",
        "",
        f"## 仅 web_search 类用例 ({len(web_search_cases)} 个)",
        f"- Mode A 命中: {rule_web}/{len(web_search_cases)} = "
        f"{rule_web / len(web_search_cases):.1%}"
        if web_search_cases
        else "- Mode A: 0/0",
        f"- Mode B 命中: {plan_c_web}/{len(web_search_cases)} = "
        f"{plan_c_web / len(web_search_cases):.1%}"
        if web_search_cases
        else "- Mode B: 0/0",
        f"- Mode C 命中: {hybrid_web}/{len(web_search_cases)} = "
        f"{hybrid_web / len(web_search_cases):.1%}"
        if web_search_cases
        else "- Mode C: 0/0",
        "",
        "## 耗时统计",
        "### Mode B (LLM 自选)",
        f"- 总耗时: {total_llm_lat} ms | 平均: {avg_llm_lat:.0f} ms | "
        f"最大: {max_llm_lat} ms | 最小: {min_llm_lat} ms",
        "- 每 case 成本: 1 次 LLM 调用",
        "",
        "### Mode C (BM25+向量)",
        f"- 总耗时: {total_hybrid_lat} ms | 平均: {avg_hybrid_lat:.0f} ms | "
        f"最大: {max_hybrid_lat} ms | 最小: {min_hybrid_lat} ms",
        f"- 向量索引命中 case 数: {vec_used_count}/{total}",
        "- 每 case 成本: 0 次 LLM 调用 (纯算法)",
        f"- 速度比 Mode B 快约 {avg_llm_lat / max(avg_hybrid_lat, 1):.1f}x",
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
    lines.append(f"- **期望工具**: `{r.case.expect_tool}`")
    lines.append(f"- **备注**: {r.case.note}")
    if r.error:
        lines.append(f"- ❌ **LLM 调用失败**: `{r.error}`")
        return lines
    lines.append(f"- **规则允许 web_search**: {r.rule_allows_web_search}")
    lines.append(
        f"- **Mode C BM25+向量 top3**: `{r.hybrid_top_tools}` "
        f"(向量={'on' if r.hybrid_vector_used else 'off'}, "
        f"{r.hybrid_latency_ms}ms)"
    )
    lines.append(
        f"- **Mode B LLM 自选**: `{r.llm_chosen_tools}` ({r.llm_latency_ms}ms)"
    )
    lines.append(
        f"- Mode A (current_rule): {'✅ 命中' if r.rule_hits else '❌ 未命中'}"
    )
    lines.append(
        f"- Mode B (plan_c LLM 自选): {'✅ 命中' if r.plan_c_hits else '❌ 未命中'}"
    )
    lines.append(
        f"- Mode C (BM25+向量 top3): {'✅ 命中' if r.hybrid_hits else '❌ 未命中'}"
    )
    return lines


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Router 方案 C Spike")
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help=f"测试用例 YAML 路径, 默认: {DEFAULT_CASES_PATH.name}",
    )
    parser.add_argument("--json", dest="json_path", help="JSON 报告输出路径")
    parser.add_argument("--report", help="Markdown 报告输出路径")
    parser.add_argument("-v", "--verbose", action="store_true")
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
            json.dumps([r.to_payload() for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON 报告已写入: {args.json_path}")
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"Markdown 报告已写入: {args.report}")


if __name__ == "__main__":
    main()
