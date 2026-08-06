"""Agent Reflection 控制层。"""

from app.agent.reflector.models import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)

__all__ = [
    "ReflectionDecision",
    "ReflectionIssue",
    "ReflectionResult",
    "ReflectionSeverity",
    "ReflectionTrigger",
    "ReflectorService",
    "has_write_success_claim",
]


def __getattr__(name: str):
    if name == "ReflectorService":
        from app.agent.reflector.service import ReflectorService

        return ReflectorService
    if name == "has_write_success_claim":
        from app.agent.reflector.checks import first_write_success_phrase

        return lambda text: first_write_success_phrase(text) is not None
    raise AttributeError(name)
