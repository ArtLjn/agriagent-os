"""Skill Router 服务入口。"""

import logging
import time
from copy import deepcopy
from dataclasses import replace

from langchain_core.tools import BaseTool

from app.agent.router.catalog import SkillCatalog
from app.agent.router.candidate_retriever import CandidateRetriever
from app.agent.router.hybrid_retriever import HybridOperationRetriever
from app.agent.router.skill_vector_store import build_skill_vector_search_fn
from app.agent.router import classifier_signals as signals
from app.agent.router.classifier import RuleIntentClassifier
from app.agent.router.intent import IntentType, classify_intent
from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)
from app.agent.router.policy import RouterPolicy
from app.agent.router.trace_diagnostics import (
    candidate_explanations,
    selection_path,
    with_trace_diagnostics,
)
from app.infra.trace_context import get_trace
from app.shared.logging import log_event
from app.skills.registry import OperationDefinition, load_skill_registry


logger = logging.getLogger(__name__)
_READ_OPERATION_RISKS = frozenset({"read", "external_network"})
_WRITE_OPERATION_RISKS = frozenset({"write_confirm", "write_high"})
_RETRIEVABLE_READ_HINTS = (
    "查询",
    "查看",
    "看看",
    "看一下",
    "有哪些",
    "多少",
    "还欠",
    "未付",
    "未结清",
    "没结清",
    "列表",
    "明细",
    "统计",
    "show",
    "list",
    "how much",
    "what",
    "which",
    "remaining",
    "remain",
    "unpaid",
)
_RETRIEVABLE_READ_ENTITY_HINTS = (
    "欠款",
    "欠",
    "未付",
    "未结清",
    "没结清",
    "账",
    "钱",
    "花",
    "成本",
    "费用",
    "支出",
    "工资",
    "人工",
    "工人",
    "地块",
    "棚",
    "作物",
    "种植",
    "周期",
    "天气",
    "分类",
    "单位",
    "debt",
    "payable",
    "cost",
    "expense",
    "wage",
    "labor",
    "worker",
    "weather",
)


class SkillRouter:
    """组合 catalog、classifier 与 policy 的路由服务。"""

    def __init__(
        self,
        classifier: RuleIntentClassifier | None = None,
        policy: RouterPolicy | None = None,
        budget: DisclosureBudget | None = None,
    ) -> None:
        self._classifier = classifier or RuleIntentClassifier()
        self._budget = budget or DisclosureBudget()
        self._policy = policy or RouterPolicy(self._budget)
        self._retriever = CandidateRetriever()
        self._hybrid_retriever = HybridOperationRetriever(
            vector_search=build_skill_vector_search_fn()
        )

    def route(self, message: str, tools: list[BaseTool]) -> RouterDecision:
        """根据用户输入和可用工具返回路由决策。"""
        started_at = time.perf_counter()
        self._log_route_started(message=message, tools=tools)
        catalog = SkillCatalog.from_tools(tools)
        try:
            frames, intent = self._classified_frames(message, catalog)
            frames, early_decision = self._resolve_retrieval_frames(
                message,
                catalog,
                frames,
                intent,
            )
            if early_decision is not None:
                early_decision = with_trace_diagnostics(
                    early_decision,
                    vector_index_enabled=self._hybrid_retriever.vector_index_enabled,
                )
                self._log_route_completed(
                    started_at=started_at,
                    decision=early_decision,
                    candidate_count=len(catalog.candidates()),
                )
                return early_decision
            decision = self._policy.apply(
                message=message,
                frames=frames,
                candidates=catalog.candidates(),
            )
            decision = with_trace_diagnostics(
                decision,
                vector_index_enabled=self._hybrid_retriever.vector_index_enabled,
            )
        except Exception as exc:
            self._log_route_failed(
                started_at=started_at,
                error_code=exc.__class__.__name__,
            )
            raise
        self._log_route_completed(
            started_at=started_at,
            decision=decision,
            candidate_count=len(catalog.candidates()),
        )
        return decision

    def _classified_frames(
        self,
        message: str,
        catalog: SkillCatalog,
    ) -> tuple[list[IntentFrame], IntentType]:
        frames = self._enrich_frames(self._classifier.classify(message), catalog)
        intent = classify_intent(message)
        self._log_classification_completed(frames=frames, intent=intent)
        if frames:
            self._log_vector_recall_skipped(
                reason="rule_classifier_matched",
                intent=intent,
                frame_count=len(frames),
                retrievable_read=self._looks_like_retrievable_read(message),
            )
        return frames, intent

    def _resolve_retrieval_frames(
        self,
        message: str,
        catalog: SkillCatalog,
        frames: list[IntentFrame],
        intent: IntentType,
    ) -> tuple[list[IntentFrame], RouterDecision | None]:
        if frames:
            return frames, None
        if intent == IntentType.WRITE:
            return self._write_retrieval_frames(message, catalog, intent)
        if self._looks_like_retrievable_read(message):
            return self._retrieved_frames(message, catalog), None
        self._log_vector_recall_skipped(
            reason="not_retrievable_read",
            intent=intent,
            frame_count=0,
            retrievable_read=False,
        )
        return frames, None

    def _write_retrieval_frames(
        self,
        message: str,
        catalog: SkillCatalog,
        intent: IntentType,
    ) -> tuple[list[IntentFrame], RouterDecision | None]:
        frames = self._retrieved_write_frames(message, catalog)
        if frames:
            self._log_vector_recall_skipped(
                reason="write_candidate_retriever",
                intent=intent,
                frame_count=len(frames),
                retrievable_read=False,
            )
            return frames, None
        self._log_vector_recall_skipped(
            reason="unresolved_write",
            intent=intent,
            frame_count=0,
            retrievable_read=False,
        )
        return frames, self._unresolved_write_decision(message)

    @staticmethod
    def _log_route_started(*, message: str, tools: list[BaseTool]) -> None:
        trace = get_trace()
        log_event(
            logger,
            logging.INFO,
            "skill_router_started",
            request_id=trace.request_id if trace else None,
            session_id=trace.session_id if trace else None,
            status="started",
            data={
                "message_len": len(message),
                "tool_count": len(tools),
            },
        )

    def _log_classification_completed(
        self,
        *,
        frames: list[IntentFrame],
        intent: IntentType,
    ) -> None:
        trace = get_trace()
        log_event(
            logger,
            logging.INFO,
            "skill_router_classification_completed",
            request_id=trace.request_id if trace else None,
            session_id=trace.session_id if trace else None,
            status="success",
            data={
                "coarse_intent": intent.value,
                "frame_count": len(frames),
                "frame_intents": [frame.intent for frame in frames],
                "frame_capabilities": [frame.capability for frame in frames],
                "frame_operations": [frame.operation for frame in frames],
            },
        )

    def _log_vector_recall_skipped(
        self,
        *,
        reason: str,
        intent: IntentType,
        frame_count: int,
        retrievable_read: bool,
    ) -> None:
        trace = get_trace()
        log_event(
            logger,
            logging.INFO,
            "skill_router_vector_recall_skipped",
            request_id=trace.request_id if trace else None,
            session_id=trace.session_id if trace else None,
            status="skipped",
            data={
                "reason": reason,
                "coarse_intent": intent.value,
                "frame_count": frame_count,
                "retrievable_read": retrievable_read,
                "vector_index_enabled": self._hybrid_retriever.vector_index_enabled,
                "vector_search_used": False,
                "quillrag_retrieve_used": False,
                "external_embedding_requested": False,
                "embedding_location": "none",
                "local_embedding_used": False,
                "local_query_embedding_calls": 0,
                "local_doc_embedding_calls": 0,
            },
        )

    @staticmethod
    def _log_route_completed(
        *,
        started_at: float,
        decision: RouterDecision,
        candidate_count: int,
    ) -> None:
        trace = get_trace()
        log_event(
            logger,
            logging.INFO,
            "skill_router_completed",
            request_id=trace.request_id if trace else None,
            session_id=trace.session_id if trace else None,
            status="success",
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            data={
                "candidate_count": candidate_count,
                "selected_tools": decision.selected_tools,
                "selected_operations": decision.selected_operations,
                "selection_path": selection_path(decision),
                "selection_reason": decision.reason,
                "recall": decision.evidence.get("recall"),
                "candidate_explanations": {
                    "items": decision.evidence.get(
                        "candidate_explanations",
                        candidate_explanations(decision),
                    )
                },
                "fallback": decision.fallback,
                "fallback_reason": decision.fallback_reason,
                "policy_violations": decision.policy_violations,
            },
        )

    @staticmethod
    def _log_route_failed(*, started_at: float, error_code: str) -> None:
        trace = get_trace()
        log_event(
            logger,
            logging.WARNING,
            "skill_router_completed",
            code=error_code,
            request_id=trace.request_id if trace else None,
            session_id=trace.session_id if trace else None,
            status="failed",
            duration_ms=int((time.perf_counter() - started_at) * 1000),
        )

    def _retrieved_frames(
        self,
        message: str,
        catalog: SkillCatalog,
    ) -> list[IntentFrame]:
        read_candidates = self._read_operation_candidates(catalog)
        retrieved = self._hybrid_retriever.retrieve(
            message,
            read_candidates,
            limit=len(read_candidates),
        )
        selected_candidates = self._filter_retrieved_candidates(
            message,
            retrieved.selected_candidates,
            scores=retrieved.scores,
        )
        if not selected_candidates:
            return []
        frames: list[IntentFrame] = []
        seen_names: set[str] = set()
        for candidate in selected_candidates:
            if candidate.name in seen_names:
                continue
            seen_names.add(candidate.name)
            frames.append(
                IntentFrame(
                    domain=candidate.domain,
                    intent="retrieved_candidate",
                    risk="read",
                    capability=candidate.capability,
                    operation=candidate.operation,
                    operation_hint=candidate.operation,
                    candidate_tools=[candidate.name],
                    confidence=0.6,
                    score=0.6,
                    evidence={
                        "source": "hybrid_operation_retriever",
                        "recall": retrieved.recall,
                        "top_candidates": retrieved.top_candidates,
                        "scores": retrieved.scores,
                        "retrieval_evidence": {
                            self._route_key(candidate): retrieved.evidence.get(
                                self._route_key(candidate),
                                {},
                            )
                        },
                    },
                )
            )
            if len(frames) >= self._budget.max_retrieved_tools_default:
                break
        return frames

    @staticmethod
    def _filter_retrieved_candidates(
        message: str,
        candidates: list[ToolCandidate],
        *,
        scores: dict[str, float],
    ) -> list[ToolCandidate]:
        candidates = _filter_low_confidence_retrieved_candidates(candidates, scores)
        names = [candidate.name for candidate in candidates]
        if (
            "manage_crop_cycle" not in names
            or "manage_planting_units" not in names
            or signals.looks_like_planting_unit_query(message)
        ):
            return candidates
        return [
            candidate
            for candidate in candidates
            if candidate.name != "manage_planting_units"
        ]

    @staticmethod
    def _route_key(candidate: ToolCandidate) -> str:
        if candidate.operation:
            return f"{candidate.name}.{candidate.operation}"
        return candidate.name

    def _retrieved_write_frames(
        self,
        message: str,
        catalog: SkillCatalog,
    ) -> list[IntentFrame]:
        write_candidates = self._write_operation_candidates(catalog)
        retrieved = self._retriever.retrieve(
            message,
            write_candidates,
            limit=1,
        )
        if not retrieved.selected_names:
            return []
        frames: list[IntentFrame] = []
        for candidate in retrieved.selected_candidates:
            name = candidate.name
            frames.append(
                IntentFrame(
                    domain=candidate.domain,
                    intent="retrieved_write_candidate",
                    risk=candidate.risk,
                    capability=candidate.capability,
                    operation=candidate.operation,
                    operation_hint=candidate.operation,
                    candidate_tools=[name],
                    confidence=0.62,
                    score=max(candidate.score, 0.62),
                    params_hint={"operation": candidate.operation}
                    if candidate.operation
                    else None,
                    evidence={
                        "source": "candidate_retriever",
                        "coarse_intent": "write",
                        "scores": retrieved.scores,
                        "retrieval_evidence": {name: retrieved.evidence.get(name, {})},
                    },
                    requires_confirmation=True,
                )
            )
        return frames

    @staticmethod
    def _write_operation_candidates(catalog: SkillCatalog) -> list[ToolCandidate]:
        candidates = list(catalog.candidates())
        write_candidates = [
            candidate
            for candidate in candidates
            if candidate.risk in _WRITE_OPERATION_RISKS
        ]
        try:
            registry = load_skill_registry()
        except (OSError, ValueError):
            return write_candidates

        existing_keys = {
            (candidate.name, candidate.capability, candidate.operation)
            for candidate in write_candidates
        }
        for candidate in candidates:
            if not candidate.capability or candidate.operation is not None:
                continue
            capability = registry.capabilities.get(candidate.capability)
            if capability is None:
                continue
            for operation in capability.operations.values():
                if operation.risk not in _WRITE_OPERATION_RISKS:
                    continue
                key = (candidate.name, candidate.capability, operation.name)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                write_candidates.append(
                    SkillRouter._operation_candidate(candidate, operation)
                )
        return write_candidates

    @staticmethod
    def _read_operation_candidates(catalog: SkillCatalog) -> list[ToolCandidate]:
        candidates = list(catalog.candidates())
        read_candidates = [
            candidate for candidate in candidates if candidate.risk in _READ_OPERATION_RISKS
        ]
        try:
            registry = load_skill_registry()
        except (OSError, ValueError):
            return read_candidates

        existing_keys = {
            (candidate.name, candidate.capability, candidate.operation)
            for candidate in read_candidates
        }
        for candidate in candidates:
            if not candidate.capability or candidate.operation is not None:
                continue
            capability = registry.capabilities.get(candidate.capability)
            if capability is None:
                continue
            for operation in capability.operations.values():
                if operation.risk not in _READ_OPERATION_RISKS:
                    continue
                key = (candidate.name, candidate.capability, operation.name)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                read_candidates.append(
                    SkillRouter._operation_candidate(candidate, operation)
                )
        return read_candidates

    @staticmethod
    def _operation_candidate(
        candidate: ToolCandidate,
        operation: OperationDefinition,
    ) -> ToolCandidate:
        return replace(
            candidate,
            risk=operation.risk,
            operation=operation.name,
            operation_risk=operation.risk,
            legacy_alias=(
                operation.legacy_aliases[0]
                if operation.legacy_aliases
                else candidate.legacy_alias
            ),
            intents=[
                operation.name,
                candidate.capability or "",
                candidate.name,
                *list(operation.legacy_aliases),
            ],
            trigger_examples=[
                *candidate.trigger_examples,
                operation.description,
            ],
            candidate_group=f"{candidate.domain}_{operation.risk}",
            evidence={
                **candidate.evidence,
                "source": "skill_registry_operation",
                "operation": operation.name,
                "operation_risk": operation.risk,
            },
        )

    @staticmethod
    def _unresolved_write_decision(message: str) -> RouterDecision:
        return RouterDecision(
            selected_tools=[],
            fallback="write_intent_unresolved",
            fallback_reason="write_intent_without_candidate",
            reason="已识别写入意图，但未匹配到可用能力",
            clarification=(
                "我理解这是要记录或修改业务数据，但当前没有生成可确认的写入动作。"
                "请补充要处理的对象、动作、金额或时间等关键信息。"
            ),
            evidence={"coarse_intent": "write", "message": message[:200]},
        )

    @staticmethod
    def _read_operation_for(candidate: ToolCandidate | None) -> str | None:
        if candidate is None or not candidate.capability:
            return None
        if candidate.operation and candidate.risk in _READ_OPERATION_RISKS:
            return candidate.operation
        try:
            capability = load_skill_registry().capabilities.get(candidate.capability)
        except (OSError, ValueError):
            return None
        if capability is None:
            return None
        for operation in capability.operations.values():
            if operation.risk in _READ_OPERATION_RISKS:
                return operation.name
        return None

    @staticmethod
    def _looks_like_retrievable_read(message: str) -> bool:
        normalized = message.strip().lower()
        return any(hint in normalized for hint in _RETRIEVABLE_READ_HINTS) and any(
            hint in normalized for hint in _RETRIEVABLE_READ_ENTITY_HINTS
        )

    def build_pending_plan_steps(self, decision: RouterDecision) -> list[dict]:
        """把多写入意图帧转换为 pending plan 存储步骤。"""
        write_frames = [
            frame
            for frame in decision.frames
            if frame.requires_confirmation and frame.params_hint
        ]
        if len(write_frames) < 2:
            return []

        return [
            {
                "step_id": frame.intent,
                "tool_name": self._tool_name_for_frame(frame),
                "params": self._params_for_frame(frame),
                "depends_on": list(frame.depends_on),
            }
            for frame in write_frames
        ]

    @staticmethod
    def _tool_name_for_frame(frame: IntentFrame) -> str:
        if frame.intent == "create_worker":
            return "manage_workers"
        if frame.intent == "create_work_order":
            return "create_operation_work_order"
        return frame.candidate_tools[0] if frame.candidate_tools else frame.intent

    @staticmethod
    def _enrich_frames(
        frames: list[IntentFrame],
        catalog: SkillCatalog,
    ) -> list[IntentFrame]:
        """把 Registry catalog metadata 合并到兼容 IntentFrame。"""
        enriched: list[IntentFrame] = []
        for frame in frames:
            matched = [
                candidate
                for name in frame.candidate_tools
                if (candidate := catalog.get(name)) is not None
            ]
            if not matched:
                enriched.append(frame)
                continue
            best = SkillRouter._best_candidate_for_frame(frame, matched)
            enriched.append(
                replace(
                    frame,
                    candidate_tools=SkillRouter._canonical_candidate_names(matched),
                    capability=frame.capability or best.capability,
                    operation=frame.operation or best.operation,
                    operation_hint=frame.operation_hint or best.operation,
                    score=max(frame.score, best.score),
                    evidence={
                        **frame.evidence,
                        "domain_scores": SkillRouter._domain_scores(frame, matched),
                        "capability_scores": SkillRouter._capability_scores(matched),
                        "operation_scores": SkillRouter._operation_scores(matched),
                        "matched_candidates": [
                            SkillRouter._candidate_evidence(candidate)
                            for candidate in matched
                        ],
                    },
                )
            )
        return enriched

    @staticmethod
    def _canonical_candidate_names(candidates: list[ToolCandidate]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.name in seen:
                continue
            names.append(candidate.name)
            seen.add(candidate.name)
        return names

    @staticmethod
    def _best_candidate_for_frame(
        frame: IntentFrame,
        candidates: list[ToolCandidate],
    ) -> ToolCandidate:
        def candidate_score(candidate: ToolCandidate) -> float:
            score = candidate.score
            if candidate.domain == frame.domain:
                score += 0.2
            if candidate.operation and candidate.operation in frame.intent:
                score += 0.2
            if candidate.name in frame.candidate_tools[:1]:
                score += 0.1
            return score

        return max(candidates, key=candidate_score)

    @staticmethod
    def _domain_scores(
        frame: IntentFrame,
        candidates: list[ToolCandidate],
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for candidate in candidates:
            base_score = 1.0 if candidate.domain == frame.domain else 0.75
            scores[candidate.domain] = max(
                scores.get(candidate.domain, 0.0), base_score
            )
        return scores

    @staticmethod
    def _capability_scores(candidates: list[ToolCandidate]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for candidate in candidates:
            if not candidate.capability:
                continue
            scores[candidate.capability] = max(
                scores.get(candidate.capability, 0.0),
                candidate.score or 0.85,
            )
        return scores

    @staticmethod
    def _operation_scores(candidates: list[ToolCandidate]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for candidate in candidates:
            if not candidate.operation:
                continue
            scores[candidate.operation] = max(
                scores.get(candidate.operation, 0.0),
                candidate.score or 0.85,
            )
        return scores

    @staticmethod
    def _candidate_evidence(candidate: ToolCandidate) -> dict:
        return {
            "name": candidate.name,
            "domain": candidate.domain,
            "capability": candidate.capability,
            "operation": candidate.operation,
            "risk": candidate.risk,
            "enabled": candidate.enabled,
            "legacy_alias": candidate.legacy_alias,
            "score": candidate.score or 0.85,
        }

    @staticmethod
    def _params_for_frame(frame: IntentFrame) -> dict:
        params = deepcopy(frame.params_hint or {})
        if frame.intent == "create_worker":
            params.setdefault("action", "create")
        if frame.intent == "create_work_order":
            for key in ("workers", "unit_names"):
                if isinstance(params.get(key), list):
                    params[key] = ",".join(str(item) for item in params[key])
        return params


def _filter_low_confidence_retrieved_candidates(
    candidates: list[ToolCandidate],
    scores: dict[str, float],
) -> list[ToolCandidate]:
    if not candidates:
        return []
    route_scores = [
        scores.get(SkillRouter._route_key(candidate), 0.0) for candidate in candidates
    ]
    top_score = max(route_scores, default=0.0)
    if top_score <= 0:
        return candidates
    threshold = max(0.18, top_score * 0.5)
    kept = [
        candidate
        for candidate, score in zip(candidates, route_scores, strict=True)
        if score >= threshold
    ]
    return kept or candidates[:1]
