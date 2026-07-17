"""Router policy 候选选择状态与预算辅助逻辑。"""

from dataclasses import dataclass, field

from app.agent.router.models import DisclosureBudget, IntentFrame, ToolCandidate
from app.agent.router.policy_trace import rejected_candidate as rejected_payload


@dataclass
class SelectionState:
    """Policy 选择过程中的可变状态。"""

    selected: list[ToolCandidate] = field(default_factory=list)
    rejected_tools: list[str] = field(default_factory=list)
    rejected_candidates: list[dict] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)
    write_count: int = 0
    schema_token_estimate: int = 0


def select_candidate(state: SelectionState, candidate: ToolCandidate) -> None:
    state.selected.append(candidate)
    state.schema_token_estimate += candidate.schema_token_estimate
    if candidate.risk.startswith("write"):
        state.write_count += 1


def reject_candidate(
    state: SelectionState,
    name: str,
    reason: str,
    candidate: ToolCandidate | None,
    violation: str | None = None,
) -> None:
    state.rejected_tools.append(name)
    state.rejected_candidates.append(rejected_payload(name, reason, candidate))
    if violation is not None:
        append_violation(state.policy_violations, violation)


def write_budget_exceeded(
    candidate: ToolCandidate,
    state: SelectionState,
    budget: DisclosureBudget,
) -> bool:
    return (
        candidate.risk.startswith("write")
        and state.write_count >= budget.max_write_tools
    )


def schema_budget_exceeded(
    candidate: ToolCandidate,
    state: SelectionState,
    budget: DisclosureBudget,
) -> bool:
    return (
        state.schema_token_estimate + candidate.schema_token_estimate
        > budget.max_schema_tokens
    )


def collect_candidate_names(frames: list[IntentFrame]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for frame in frames:
        for name in frame.candidate_tools:
            if name in seen:
                continue
            names.append(name)
            seen.add(name)
    return names


def candidate_frame_map(frames: list[IntentFrame]) -> dict[str, IntentFrame]:
    by_name: dict[str, IntentFrame] = {}
    for frame in frames:
        for name in frame.candidate_tools:
            by_name.setdefault(name, frame)
    return by_name


def trim_candidates_by_budget(
    candidates: list[ToolCandidate],
    budget: DisclosureBudget,
    max_tools: int,
) -> list[ToolCandidate]:
    selected: list[ToolCandidate] = []
    tokens = 0
    for candidate in candidates:
        if len(selected) >= max_tools:
            break
        next_tokens = tokens + candidate.schema_token_estimate
        if next_tokens > budget.max_schema_tokens:
            break
        selected.append(candidate)
        tokens = next_tokens
    return selected


def dedupe_context_dependencies(
    selected: list[ToolCandidate],
    frames: list[IntentFrame],
) -> list[str]:
    dependencies: list[str] = []
    for candidate in selected:
        dependencies.extend(candidate.context_dependencies)
    for frame in frames:
        dependencies.extend(frame.depends_on)
    return dedupe(dependencies)


def dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def append_violation(violations: list[str], violation: str) -> None:
    if violation not in violations:
        violations.append(violation)


def with_violation(violations: list[str], violation: str) -> list[str]:
    updated = list(violations)
    append_violation(updated, violation)
    return updated
