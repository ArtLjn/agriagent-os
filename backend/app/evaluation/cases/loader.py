"""评测用例加载器。"""

import json
from pathlib import Path
from typing import Any

from app.evaluation.cases.schemas import (
    AgentReplayCase,
    ContextExpectation,
    ExpectedSkillCall,
    ExpectedWriteOperation,
    ReplyAssertion,
)
from app.simulation.test_runner import CASES_DIR


def load_simulation_cases(
    cases_dir: Path = CASES_DIR,
    category: str | None = None,
) -> list[AgentReplayCase]:
    """复用现有 simulation JSON 用例并转换为 AgentReplayCase。"""
    cases: list[AgentReplayCase] = []
    if not cases_dir.exists():
        return cases

    for path in sorted(cases_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            raw_cases = json.load(file)
        if not isinstance(raw_cases, list):
            continue
        for raw in raw_cases:
            replay_case = _simulation_to_replay_case(raw, source_file=path.name)
            if category is None or replay_case.category == category:
                cases.append(replay_case)
    return cases


def load_replay_cases(path: Path) -> list[AgentReplayCase]:
    """加载原生 Agent 回放用例 JSON。"""
    with path.open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    if not isinstance(raw_cases, list):
        raise ValueError("replay cases must be a JSON array")
    return [_raw_to_replay_case(raw) for raw in raw_cases]


def _simulation_to_replay_case(
    raw: dict[str, Any], source_file: str
) -> AgentReplayCase:
    expected_writes = [
        ExpectedWriteOperation(
            table=table,
            operation="insert" if spec.get("added", 0) else "unknown",
            expected_count=spec.get("added", 0),
            match_fields=spec.get("match_fields", {}),
        )
        for table, spec in raw.get("expected_db_changes", {}).items()
    ]
    return AgentReplayCase(
        case_id=raw["case_id"],
        description=raw["description"],
        user_input=raw["user_input"],
        expected_skills=[],
        expected_writes=expected_writes,
        reply_assertions=[
            ReplyAssertion(contains=keyword)
            for keyword in raw.get("expected_response_matches", [])
        ],
        context=ContextExpectation(
            farm_context=raw.get("precondition", {}),
            required_facts=[],
        ),
        category=raw.get("category", "basic"),
        metadata={"source": "simulation", "source_file": source_file},
    )


def _raw_to_replay_case(raw: dict[str, Any]) -> AgentReplayCase:
    return AgentReplayCase(
        case_id=raw["case_id"],
        description=raw.get("description", ""),
        user_input=raw["user_input"],
        user_context=raw.get("user_context", {}),
        context=_raw_context(raw.get("context", {})),
        expected_skills=[
            ExpectedSkillCall(
                name=item["name"],
                arguments=item.get("arguments", {}),
                required=item.get("required", True),
            )
            for item in raw.get("expected_skills", [])
        ],
        expected_writes=[
            ExpectedWriteOperation(
                table=item["table"],
                operation=item.get("operation", "unknown"),
                expected_count=item.get("expected_count", 1),
                match_fields=item.get("match_fields", {}),
                requires_confirmation=item.get("requires_confirmation", False),
            )
            for item in raw.get("expected_writes", [])
        ],
        reply_assertions=[
            ReplyAssertion(
                contains=item.get("contains"),
                not_contains=item.get("not_contains"),
                min_length=item.get("min_length", 0),
            )
            for item in raw.get("reply_assertions", [])
        ],
        category=raw.get("category", "basic"),
        metadata=raw.get("metadata", {}),
    )


def _raw_context(raw: dict[str, Any]) -> ContextExpectation:
    return ContextExpectation(
        user_context=raw.get("user_context", {}),
        farm_context=raw.get("farm_context", {}),
        required_facts=raw.get("required_facts", []),
        expected_block_types=raw.get("expected_block_types", []),
    )
