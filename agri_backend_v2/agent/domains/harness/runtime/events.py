"""Harness Runtime 的领域事件边界。

Runtime 只产生 type/data 领域事件；Redis/SSE 适配层负责补充 seq、event_id
以及传输格式，避免业务循环直接依赖 SSE wire format。
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class DomainEvent(TypedDict, total=False):
    type: str
    data: dict[str, Any]
    turn_id: str
    step: int


class EventPublisher(Protocol):
    """持久化/传输层发布器，Runtime 不关心实现介质。"""

    async def publish(self, turn_id: str, event: DomainEvent) -> int:
        ...


def domain_event(event_type: str, data: dict[str, Any] | None = None) -> DomainEvent:
    """构造不含传输游标的领域事件。"""
    return {"type": event_type, "data": data or {}}


__all__ = ["DomainEvent", "EventPublisher", "domain_event"]
