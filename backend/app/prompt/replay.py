"""Prompt 变更回放评测入口。"""

from dataclasses import dataclass

from app.prompt.models import PromptInput
from app.prompt.registry import PromptRegistry
from app.prompt.renderer import render_prompt_input


@dataclass(frozen=True)
class PromptReplayCase:
    """Prompt 回放用例。"""

    name: str
    prompt_name: str
    prompt_input: PromptInput


@dataclass(frozen=True)
class PromptReplayComparison:
    """两个 Prompt 版本的手动比较结果。"""

    case_name: str
    prompt_name: str
    base_version: str
    candidate_version: str
    base_output: str
    candidate_output: str
    changed: bool


def compare_prompt_versions(
    registry: PromptRegistry,
    replay_case: PromptReplayCase,
    base_version: str,
    candidate_version: str,
) -> PromptReplayComparison:
    """手动比较同一回放用例在两个 Prompt 版本下的渲染差异。"""
    base_output = render_prompt_input(
        replay_case.prompt_name,
        replay_case.prompt_input,
        registry=registry,
        version=base_version,
    )
    candidate_output = render_prompt_input(
        replay_case.prompt_name,
        replay_case.prompt_input,
        registry=registry,
        version=candidate_version,
    )
    return PromptReplayComparison(
        case_name=replay_case.name,
        prompt_name=replay_case.prompt_name,
        base_version=base_version,
        candidate_version=candidate_version,
        base_output=base_output,
        candidate_output=candidate_output,
        changed=base_output != candidate_output,
    )
