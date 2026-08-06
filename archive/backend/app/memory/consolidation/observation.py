"""观察事件入口。"""

from app.memory.schemas import MemoryObservationEvent


class InMemoryObservationEventSink:
    """保存对话观察事件，后续可替换为队列或异步沉淀任务。"""

    def __init__(self) -> None:
        self._events: list[MemoryObservationEvent] = []

    @property
    def events(self) -> list[MemoryObservationEvent]:
        return list(self._events)

    async def submit(self, event: MemoryObservationEvent) -> MemoryObservationEvent:
        self._events.append(event)
        return event
