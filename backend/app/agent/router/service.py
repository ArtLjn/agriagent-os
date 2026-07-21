"""Skill Router 服务入口。"""

from copy import deepcopy
from dataclasses import replace

from langchain_core.tools import BaseTool

from app.agent.router.catalog import SkillCatalog
from app.agent.router.candidate_retriever import CandidateRetriever
from app.agent.router.classifier import RuleIntentClassifier
from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)
from app.agent.router.policy import RouterPolicy
from app.skills.registry import load_skill_registry


_READ_OPERATION_RISKS = frozenset({"read", "external_network"})
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

    def route(self, message: str, tools: list[BaseTool]) -> RouterDecision:
        """根据用户输入和可用工具返回路由决策。"""
        catalog = SkillCatalog.from_tools(tools)
        frames = self._enrich_frames(self._classifier.classify(message), catalog)
        if not frames and self._looks_like_retrievable_read(message):
            frames = self._retrieved_frames(message, catalog)
        return self._policy.apply(
            message=message,
            frames=frames,
            candidates=catalog.candidates(),
        )

    def _retrieved_frames(
        self,
        message: str,
        catalog: SkillCatalog,
    ) -> list[IntentFrame]:
        retrieved = self._retriever.retrieve(
            message,
            catalog.candidates(),
            limit=self._budget.max_retrieved_tools_default,
        )
        if not retrieved.selected_names:
            return []
        frames: list[IntentFrame] = []
        for name in retrieved.selected_names:
            candidate = catalog.get(name)
            operation = self._read_operation_for(candidate)
            frames.append(
                IntentFrame(
                    domain=candidate.domain if candidate else "general",
                    intent="retrieved_candidate",
                    risk="read",
                    capability=candidate.capability if candidate else None,
                    operation=operation,
                    operation_hint=operation,
                    candidate_tools=[name],
                    confidence=0.6,
                    score=0.6,
                    evidence={
                        "source": "candidate_retriever",
                        "scores": retrieved.scores,
                        "retrieval_evidence": {name: retrieved.evidence.get(name, {})},
                    },
                )
            )
        return frames

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
        return any(hint in normalized for hint in _RETRIEVABLE_READ_HINTS)

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
