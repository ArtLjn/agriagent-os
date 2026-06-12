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
]


def __getattr__(name: str):
    if name == "ReflectorService":
        from app.agent.reflector.service import ReflectorService

        return ReflectorService
    raise AttributeError(name)
