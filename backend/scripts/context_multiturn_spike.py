"""Context 多轮对话 Spike — 完整模拟主链路的 context 构造/注入/压缩。

跑真链路:
  1. 持久化 ConversationMessage (用临时 session_id, 跑完清理)
  2. ContextPackService.build(...) 拿会话层 summary + recent_messages
  3. ContextBuilder.build_runtime_context_bundle(...) 拿预算化 bundle
  4. evaluate_task_state_relevance(...) 看承接判定
  5. MemoryService.maybe_summarize(...) 同步触发 LLM summary
  6. dump 当轮 conversation.summary / bundle.summary() / relevance 决策

每个 scenario 一份 turn-by-turn 报告, 含:
  - summary 触发时机 (LLM 调用耗时)
  - bundle 中 blocks / compressed_blocks / dropped_blocks
  - relevance 分数 + should_inject
  - token 估算曲线

用法:
    .venv/bin/python -m scripts.context_multiturn_spike
    .venv/bin/python -m scripts.context_multiturn_spike --cases path/to/cases.yaml
    .venv/bin/python -m scripts.context_multiturn_spike --report report.md --json report.json
    .venv/bin/python -m scripts.context_multiturn_spike --only long_query_summary_trigger
    .venv/bin/python -m scripts.context_multiturn_spike --keep   # 不清理 conversation
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
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

# 显式 import 所有 domain models, 让 SQLAlchemy mapper 配置通过
# (CropCycle relationship 引用 CropTemplate 等跨模块类, 不显式 import 会报错)
import app.domains.conversation.models  # noqa: F401
import app.domains.farm.models  # noqa: F401
import app.domains.finance.cost_category_models  # noqa: F401
import app.domains.finance.cost_models  # noqa: F401
import app.domains.planting.crop_models  # noqa: F401
import app.domains.planting.cycle_models  # noqa: F401
import app.domains.planting.log_models  # noqa: F401
import app.domains.planting.models  # noqa: F401
import app.domains.users.models  # noqa: F401
import app.domains.users.settings_models  # noqa: F401

from app.agent.runtime.task_state_relevance import evaluate_task_state_relevance
from app.context.builder import ContextBuilder
from app.context.core.policy import ContextBuildRequest
from app.context.pack import ContextPackService
from app.context.task_state import AgentTaskState, AgentTaskStateStore
from app.context.selectors.task_state import TaskStateSelector
from app.domains.conversation.models import Conversation, ConversationMessage
from app.domains.conversation.service import (
    async_save_message,
    get_or_create_conversation,
)
from app.memory.service import get_memory_service
from app.shared.config import settings
from app.shared.database import SessionLocal
from app.shared.llm import get_llm

logger = logging.getLogger("context_multiturn_spike")

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "context_multiturn_spike_cases.yaml"


@dataclass(frozen=True)
class SeedTask:
    task_type: str
    goal: str
    entities: dict[str, Any]
    missing_information: list[str]


@dataclass(frozen=True)
class Turn:
    user_input: str
    assistant_reply: str | None = None
    expect_summary_change: bool = False
    note: str = ""


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    farm_id: int
    summary_threshold: int
    token_budget: int
    intent: str
    selected_tool_names: list[str]
    context_dependencies: list[str]
    assistant_mode: str
    seed_active_task: SeedTask | None
    turns: list[Turn]


@dataclass
class TurnResult:
    index: int
    user_input: str
    note: str
    relevance_score: float
    relevance_decision: str
    should_inject: bool
    bundle_tokens: int
    bundle_token_budget: int
    selected_blocks: list[str]
    compressed_blocks: list[str]
    dropped_blocks: list[str]
    block_previews: dict[str, str]
    pre_summary_preview: str
    post_summary_preview: str
    summary_changed: bool
    summary_latency_ms: int
    assistant_reply_preview: str
    bundle_render_preview: str
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "user_input": self.user_input,
            "note": self.note,
            "relevance": {
                "score": self.relevance_score,
                "decision": self.relevance_decision,
                "should_inject": self.should_inject,
            },
            "bundle": {
                "token_estimate": self.bundle_tokens,
                "token_budget": self.bundle_token_budget,
                "selected_blocks": self.selected_blocks,
                "compressed_blocks": self.compressed_blocks,
                "dropped_blocks": self.dropped_blocks,
                "block_previews": self.block_previews,
                "render_preview": self.bundle_render_preview,
            },
            "summary": {
                "pre_preview": self.pre_summary_preview,
                "post_preview": self.post_summary_preview,
                "changed": self.summary_changed,
                "latency_ms": self.summary_latency_ms,
            },
            "assistant_reply_preview": self.assistant_reply_preview,
            "error": self.error,
        }


@dataclass
class ScenarioResult:
    scenario: Scenario
    session_id: str
    conversation_id: int | None
    turns: list[TurnResult] = field(default_factory=list)
    error: str | None = None
    cleaned: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.scenario.name,
            "description": self.scenario.description,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "config": {
                "summary_threshold": self.scenario.summary_threshold,
                "token_budget": self.scenario.token_budget,
                "intent": self.scenario.intent,
                "selected_tool_names": list(self.scenario.selected_tool_names),
                "context_dependencies": list(self.scenario.context_dependencies),
                "assistant_mode": self.scenario.assistant_mode,
                "seed_task": (
                    {
                        "task_type": self.scenario.seed_active_task.task_type,
                        "goal": self.scenario.seed_active_task.goal,
                        "entities": self.scenario.seed_active_task.entities,
                        "missing_information": (
                            self.scenario.seed_active_task.missing_information
                        ),
                    }
                    if self.scenario.seed_active_task
                    else None
                ),
            },
            "turns": [t.to_payload() for t in self.turns],
            "error": self.error,
            "cleaned": self.cleaned,
        }


def load_scenarios(path: Path) -> list[Scenario]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = raw.get("scenarios", []) if isinstance(raw, dict) else []
    scenarios: list[Scenario] = []
    for item in items:
        seed_raw = item.get("seed_active_task")
        seed = (
            SeedTask(
                task_type=seed_raw["task_type"],
                goal=seed_raw.get("goal", ""),
                entities=seed_raw.get("entities", {}),
                missing_information=seed_raw.get("missing_information", []),
            )
            if seed_raw
            else None
        )
        turns = [
            Turn(
                user_input=t["user_input"],
                assistant_reply=t.get("assistant_reply"),
                expect_summary_change=t.get("expect_summary_change", False),
                note=t.get("note", ""),
            )
            for t in item.get("turns", [])
        ]
        scenarios.append(
            Scenario(
                name=item["name"],
                description=item.get("description", ""),
                farm_id=int(item.get("farm_id", 2)),
                summary_threshold=int(item.get("summary_threshold", 4)),
                token_budget=int(item.get("token_budget", 800)),
                intent=item.get("intent", "query"),
                selected_tool_names=list(item.get("selected_tool_names", [])),
                context_dependencies=list(item.get("context_dependencies", [])),
                assistant_mode=item.get("assistant_mode", "echo"),
                seed_active_task=seed,
                turns=turns,
            )
        )
    return scenarios


def _preview(text: str | None, limit: int = 80) -> str:
    if not text:
        return ""
    collapsed = " ".join(str(text).split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _seed_active_task_dict(seed: SeedTask | None) -> dict | None:
    if seed is None:
        return None
    return {
        "task_type": seed.task_type,
        "goal": seed.goal,
        "entities": seed.entities,
        "missing_information": seed.missing_information,
        "next_action": "",
    }


async def _gen_assistant_reply(
    scenario: Scenario, turn: Turn, history: list[tuple[str, str]]
) -> str:
    mode = scenario.assistant_mode
    if mode == "scripted":
        if turn.assistant_reply is None:
            return "(scripted 缺 assistant_reply)"
        return turn.assistant_reply
    if mode == "echo":
        return f"(echo) 收到: {turn.user_input}"
    if mode == "llm_short":
        try:
            llm = get_llm(role="generation")
            history_text = "\n".join(
                f"{role}: {content}" for role, content in history[-6:]
            )
            prompt = (
                "你是农场助手, 用一句话(<=40 字)简短回应用户. 不要调用工具. "
                f"用户说: {turn.user_input}\n历史:\n{history_text}\n回复:"
            )
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            content = getattr(resp, "content", str(resp))
            if isinstance(content, list):
                content = " ".join(
                    str(c.get("text") if isinstance(c, dict) else c) for c in content
                )
            return str(content).strip()[:120]
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_short 失败, 降级 echo: %s", exc)
            return f"(echo) {turn.user_input}"
    return f"(unknown mode {mode}) {turn.user_input}"


def _build_bundle_summary(bundle: Any) -> dict[str, Any]:
    if bundle is None:
        return {
            "token_estimate": 0,
            "token_budget": 0,
            "selected": [],
            "compressed": [],
            "dropped": [],
            "block_previews": {},
            "render_preview": "",
        }
    block_previews: dict[str, str] = {}
    for b in getattr(bundle, "blocks", []):
        block_previews[b.key] = _preview(getattr(b, "content", ""), 100)
    return {
        "token_estimate": int(getattr(bundle, "token_estimate", 0) or 0),
        "token_budget": int(getattr(bundle, "token_budget", 0) or 0),
        "selected": [b.key for b in getattr(bundle, "blocks", [])],
        "compressed": [b.key for b in getattr(bundle, "compressed_blocks", [])],
        "dropped": [b.key for b in getattr(bundle, "dropped_blocks", [])],
        "block_previews": block_previews,
        "render_preview": _preview(getattr(bundle, "render_text", lambda: "")(), 200),
    }


async def _run_turn(
    *,
    db: Session,
    scenario: Scenario,
    turn: Turn,
    index: int,
    conversation: Conversation,
    history: list[tuple[str, str]],
    active_task: dict | None,
) -> TurnResult:
    user_msg = await async_save_message(
        db=db,
        conversation_id=conversation.id,
        role="user",
        content=turn.user_input,
    )

    pre_summary = conversation.summary or ""

    relevance = evaluate_task_state_relevance(turn.user_input, active_task)

    pack = await ContextPackService().build(
        db=db,
        farm_id=scenario.farm_id,
        session_id=conversation.session_id,
        user_id=conversation.user_id,
    )

    builder = ContextBuilder(max_tokens=scenario.token_budget)
    request = ContextBuildRequest(
        intent=scenario.intent,
        query=turn.user_input,
        selected_tool_names=list(scenario.selected_tool_names),
        context_dependencies=list(scenario.context_dependencies),
        farm_id=scenario.farm_id,
        user_id=conversation.user_id,
        session_id=conversation.session_id,
        task_state_should_inject=True,
    )
    bundle = builder.build_runtime_context_bundle(
        db=db,
        request=request,
        memory_context=None,
        context_pack=pack,
    )
    bundle_summary = _build_bundle_summary(bundle)

    summarize_started = time.perf_counter()
    try:
        await get_memory_service().maybe_summarize(
            db=db,
            conversation_id=conversation.id,
            farm_id=scenario.farm_id,
            session_id=conversation.session_id,
            messages=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("maybe_summarize 抛异常: %s", exc)
    summary_latency_ms = int((time.perf_counter() - summarize_started) * 1000)

    db.refresh(conversation)
    db.refresh(user_msg)
    post_summary = conversation.summary or ""
    summary_changed = bool(post_summary) and post_summary != pre_summary

    reply = await _gen_assistant_reply(scenario, turn, history)
    await async_save_message(
        db=db,
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
    )
    history.append(("user", turn.user_input))
    history.append(("assistant", reply))

    return TurnResult(
        index=index,
        user_input=turn.user_input,
        note=turn.note,
        relevance_score=float(relevance.score),
        relevance_decision=str(relevance.decision),
        should_inject=bool(relevance.should_inject),
        bundle_tokens=bundle_summary["token_estimate"],
        bundle_token_budget=bundle_summary["token_budget"],
        selected_blocks=bundle_summary["selected"],
        compressed_blocks=bundle_summary["compressed"],
        dropped_blocks=bundle_summary["dropped"],
        block_previews=bundle_summary["block_previews"],
        bundle_render_preview=bundle_summary["render_preview"],
        pre_summary_preview=_preview(pre_summary),
        post_summary_preview=_preview(post_summary),
        summary_changed=summary_changed,
        summary_latency_ms=summary_latency_ms,
        assistant_reply_preview=_preview(reply, 60),
    )


async def _run_scenario(scenario: Scenario, *, keep: bool) -> ScenarioResult:
    session_id = f"spike-{int(time.time())}-{scenario.name}"
    result = ScenarioResult(scenario=scenario, session_id=session_id, conversation_id=None)

    original_threshold = settings.ai.session_summary_message_threshold
    settings.ai.session_summary_message_threshold = scenario.summary_threshold
    original_storage = settings.storage.conversation_messages
    settings.storage.conversation_messages = "mysql"  # 强制 mysql 后端 (本地无 mongo)

    db = SessionLocal()
    try:
        _ensure_conversation_messages_table(db)
        conversation = get_or_create_conversation(
            db=db,
            farm_id=scenario.farm_id,
            session_id=session_id,
            user_id="context-spike",
        )
        result.conversation_id = conversation.id

        # 如果 seed 了 active task, 写到 agent_task_states 表 (TaskStateSelector 从这里读)
        if scenario.seed_active_task is not None:
            seed = scenario.seed_active_task
            AgentTaskStateStore(db).upsert_active_task(
                farm_id=scenario.farm_id,
                user_id="context-spike",
                session_id=session_id,
                task_type=seed.task_type,
                goal=seed.goal,
                entities=seed.entities,
                missing_information=seed.missing_information,
            )
            print(f"  ✓ seed task_state 已写入 agent_task_states 表", flush=True)

        active_task = _seed_active_task_dict(scenario.seed_active_task)

        history: list[tuple[str, str]] = []
        for idx, turn in enumerate(scenario.turns, start=1):
            print(
                f"  ── turn {idx}/{len(scenario.turns)} ── {turn.user_input[:40]}",
                flush=True,
            )
            try:
                turn_result = await _run_turn(
                    db=db,
                    scenario=scenario,
                    turn=turn,
                    index=idx,
                    conversation=conversation,
                    history=history,
                    active_task=active_task,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("turn 执行失败")
                turn_result = TurnResult(
                    index=idx,
                    user_input=turn.user_input,
                    note=turn.note,
                    relevance_score=0.0,
                    relevance_decision="error",
                    should_inject=False,
                    bundle_tokens=0,
                    bundle_token_budget=0,
                    selected_blocks=[],
                    compressed_blocks=[],
                    dropped_blocks=[],
                    block_previews={},
                    bundle_render_preview="",
                    pre_summary_preview="",
                    post_summary_preview="",
                    summary_changed=False,
                    summary_latency_ms=0,
                    assistant_reply_preview="",
                    error=f"{type(exc).__name__}: {exc}",
                )
            result.turns.append(turn_result)
            _print_inline_turn(turn_result)

        if not keep:
            # 清理 task_state (如果 seed 过)
            if scenario.seed_active_task is not None:
                db.query(AgentTaskState).filter(
                    AgentTaskState.session_id == session_id,
                    AgentTaskState.farm_id == scenario.farm_id,
                ).delete(synchronize_session=False)
                db.commit()
            await _cleanup_conversation(db, conversation.id)
            result.cleaned = True
        else:
            result.cleaned = False
    except Exception as exc:  # noqa: BLE001
        logger.exception("scenario 执行失败")
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        settings.ai.session_summary_message_threshold = original_threshold
        settings.storage.conversation_messages = original_storage
        db.close()

    return result


def _ensure_conversation_messages_table(db: Session) -> None:
    """本地开发环境可能没建 conversation_messages 表, 自动补建 (idempotent).

    表缺失时 repository_runtime 会 fallback 到 mongo 后端, 本地没配 mongo 就报错.
    补上表让 mysql-only 环境也能跑. 还要清掉 _missing_table_cache 否则一直走 mongo.
    """
    from sqlalchemy import text

    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INT PRIMARY KEY AUTO_INCREMENT,
                conversation_id INT NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                meta TEXT NULL,
                turn_id INT NULL,
                content_hash VARCHAR(64) NULL,
                meta_json JSON NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_conversation_messages_conversation (conversation_id),
                INDEX idx_conversation_messages_turn (turn_id)
            )
            """
        )
    )
    db.commit()

    from app.infra.repository_runtime import clear_missing_table_cache

    clear_missing_table_cache()


async def _cleanup_conversation(db: Session, conversation_id: int) -> None:
    """Conversation + ConversationMessage 都在 MySQL (脚本启动时已 ensure 表存在)."""
    from sqlalchemy import text as _sa_text

    db.execute(
        _sa_text(
            "DELETE FROM conversation_messages WHERE conversation_id = :cid"
        ),
        {"cid": conversation_id},
    )
    db.query(Conversation).filter(Conversation.id == conversation_id).delete(
        synchronize_session=False
    )
    db.commit()


def _print_inline_turn(t: TurnResult) -> None:
    flag_summary = "📝" if t.summary_changed else "  "
    flag_inject = "🔌" if t.should_inject else "  "
    print(
        f"  {flag_summary}{flag_inject} "
        f"relevance={t.relevance_score:.2f}/{t.relevance_decision} | "
        f"bundle={t.bundle_tokens}/{t.bundle_token_budget}tok "
        f"sel={len(t.selected_blocks)} cmp={len(t.compressed_blocks)} "
        f"drop={len(t.dropped_blocks)} | "
        f"summary {t.summary_latency_ms}ms",
        flush=True,
    )
    if t.error:
        print(f"    ❌ {t.error[:120]}", flush=True)


def _render_report(results: list[ScenarioResult]) -> str:
    lines: list[str] = [
        "# Context 多轮对话 Spike 报告",
        "",
        "## 总览",
        f"- scenario 数: {len(results)}",
        f"- 总轮次: {sum(len(r.turns) for r in results)}",
        f"- summary 触发次数: {sum(sum(1 for t in r.turns if t.summary_changed) for r in results)}",
        f"- bundle 压缩事件: {sum(sum(len(t.compressed_blocks) for t in r.turns) for r in results)}",
        f"- bundle 丢弃事件: {sum(sum(len(t.dropped_blocks) for t in r.turns) for r in results)}",
        "",
    ]
    for r in results:
        lines.extend(_render_scenario(r))
        lines.append("")
    return "\n".join(lines)


def _render_scenario(r: ScenarioResult) -> list[str]:
    lines = [
        f"## {r.scenario.name}",
        "",
        f"- **描述**: {r.scenario.description}",
        f"- **session**: `{r.session_id}` (cleaned={r.cleaned})",
        f"- **config**: threshold={r.scenario.summary_threshold}, "
        f"budget={r.scenario.token_budget}, intent=`{r.scenario.intent}`, "
        f"tools={r.scenario.selected_tool_names}, deps={r.scenario.context_dependencies}",
    ]
    if r.scenario.seed_active_task:
        seed = r.scenario.seed_active_task
        lines.append(
            f"- **seed task**: type=`{seed.task_type}` goal=`{seed.goal}` "
            f"entities={seed.entities} missing={seed.missing_information}"
        )
    if r.error:
        lines.append(f"- ❌ **scenario 错误**: `{r.error}`")
    lines.extend(["", "| turn | user | relevance | inject | bundle tok/budget | "
                  "sel/cmp/drop | summary | latency |", "|---|---|---|---|---|---|---|---|"])
    for t in r.turns:
        lines.append(
            f"| {t.index} | {_preview(t.user_input, 30)} | "
            f"{t.relevance_score:.2f}/{t.relevance_decision} | "
            f"{'✓' if t.should_inject else ''} | "
            f"{t.bundle_tokens}/{t.bundle_token_budget} | "
            f"{len(t.selected_blocks)}/{len(t.compressed_blocks)}/"
            f"{len(t.dropped_blocks)} | "
            f"{'📝' if t.summary_changed else ''} | "
            f"{t.summary_latency_ms}ms |"
        )
    lines.append("")
    lines.append("### 详情")
    for t in r.turns:
        lines.append(f"#### turn {t.index} — `{_preview(t.user_input, 50)}`")
        lines.append(f"- note: {t.note}")
        if t.error:
            lines.append(f"- ❌ error: `{t.error}`")
            continue
        lines.append(
            f"- relevance: score={t.relevance_score:.2f} decision=`{t.relevance_decision}` "
            f"should_inject={t.should_inject}"
        )
        lines.append(
            f"- bundle: tokens={t.bundle_tokens}/{t.bundle_token_budget} "
            f"selected={t.selected_blocks} compressed={t.compressed_blocks} "
            f"dropped={t.dropped_blocks}"
        )
        lines.append(f"- summary 触发: {'是' if t.summary_changed else '否'} "
                     f"({t.summary_latency_ms}ms)")
        if t.pre_summary_preview or t.post_summary_preview:
            lines.append(f"  - pre : {t.pre_summary_preview or '(空)'}")
            lines.append(f"  - post: {t.post_summary_preview or '(空)'}")
        lines.append(f"- assistant: {_preview(t.assistant_reply_preview, 60)}")
        lines.append("")
    return lines


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def _main_async(args: argparse.Namespace) -> int:
    # 显式触发 prompt registry 加载 (正常在 app lifespan 里做, 脚本不进 lifespan)
    from app.prompt.registry import get_registry

    try:
        get_registry().reload(settings.prompts_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt registry reload 失败: %s", exc)

    scenarios = load_scenarios(args.cases)
    if args.only:
        scenarios = [s for s in scenarios if s.name == args.only]
        if not scenarios:
            print(f"未找到 scenario: {args.only}", flush=True)
            return 2

    print(f"已加载 {len(scenarios)} 个 scenario", flush=True)
    results: list[ScenarioResult] = []
    for s in scenarios:
        print(f"\n══ scenario: {s.name} ({len(s.turns)} turns) ══", flush=True)
        result = await _run_scenario(s, keep=args.keep)
        results.append(result)

    report = _render_report(results)
    print("\n" + report)

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(
                [r.to_payload() for r in results], ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        print(f"\nJSON 报告已写入: {args.json_path}")
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"Markdown 报告已写入: {args.report}")

    return 0 if not any(r.error for r in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Context 多轮对话 Spike")
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help=f"剧本 YAML 路径, 默认: {DEFAULT_CASES_PATH.name}",
    )
    parser.add_argument("--only", help="只跑指定 name 的 scenario")
    parser.add_argument("--report", help="Markdown 报告输出路径")
    parser.add_argument("--json", dest="json_path", help="JSON 报告输出路径")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="保留测试 conversation (默认清理, 避免污染库)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    if not args.cases.exists():
        raise SystemExit(f"cases 文件不存在: {args.cases}")

    exit_code = asyncio.run(_main_async(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
