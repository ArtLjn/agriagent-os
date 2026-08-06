"""Router policy trace payload helpers。"""

from app.agent.router.models import IntentFrame, ToolCandidate


def selected_operations(selected: list[ToolCandidate]) -> dict[str, list[str]]:
    operations: dict[str, list[str]] = {}
    for candidate in selected:
        capability = candidate.capability or candidate.name
        operation = candidate.operation or candidate.name
        operations.setdefault(capability, [])
        if operation not in operations[capability]:
            operations[capability].append(operation)
    return operations


def rejected_candidate(
    name: str,
    reason: str,
    candidate: ToolCandidate | None,
) -> dict:
    payload = {"name": name, "reason": reason}
    if candidate is None:
        return payload
    payload.update(
        {
            "domain": candidate.domain,
            "capability": candidate.capability,
            "operation": candidate.operation,
            "risk": candidate.risk,
            "enabled": candidate.enabled,
            "legacy_alias": candidate.legacy_alias,
        }
    )
    return payload


def trace_scores(
    frames: list[IntentFrame],
    selected: list[ToolCandidate],
) -> dict:
    domain_scores: dict[str, float] = {}
    capability_scores: dict[str, float] = {}
    operation_scores: dict[str, float] = {}
    for frame in frames:
        _merge_scores(domain_scores, frame.evidence.get("domain_scores", {}))
        _merge_scores(capability_scores, frame.evidence.get("capability_scores", {}))
        _merge_scores(operation_scores, frame.evidence.get("operation_scores", {}))
    for candidate in selected:
        _add_candidate_scores(
            candidate,
            domain_scores,
            capability_scores,
            operation_scores,
        )
    return {
        "domain": domain_scores,
        "capability": capability_scores,
        "operation": operation_scores,
    }


def decision_evidence(
    frames: list[IntentFrame],
    selected: list[ToolCandidate],
    rejected_candidates: list[dict],
) -> dict:
    return {
        "frames": [frame.evidence for frame in frames if frame.evidence],
        "selected_candidates": [
            {
                "name": candidate.name,
                "domain": candidate.domain,
                "capability": candidate.capability,
                "operation": candidate.operation,
                "risk": candidate.risk,
                "legacy_alias": candidate.legacy_alias,
            }
            for candidate in selected
        ],
        "rejected_candidates": rejected_candidates,
    }


def _add_candidate_scores(
    candidate: ToolCandidate,
    domain_scores: dict[str, float],
    capability_scores: dict[str, float],
    operation_scores: dict[str, float],
) -> None:
    score = candidate.score or 0.85
    domain_scores[candidate.domain] = max(
        domain_scores.get(candidate.domain, 0.0), score
    )
    if candidate.capability:
        capability_scores[candidate.capability] = max(
            capability_scores.get(candidate.capability, 0.0),
            score,
        )
    if candidate.operation:
        operation_scores[candidate.operation] = max(
            operation_scores.get(candidate.operation, 0.0),
            score,
        )


def _merge_scores(target: dict[str, float], source: dict) -> None:
    for key, value in source.items():
        if not isinstance(key, str):
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        target[key] = max(target.get(key, 0.0), score)
