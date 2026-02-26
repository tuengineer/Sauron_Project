# src/market_simulator/events.py

from typing import Callable, List, Dict, Any


class ScheduledEvent:
    def __init__(self, timestamp_ms: int, callback: Callable):
        self.timestamp_ms = timestamp_ms
        self.callback = callback
        self.executed = False


class EventEngine:
    """
    Motor de eventos con timestamps simulados.
    Preparado para ICM fase 2.
    """

    def __init__(self):
        self.events: List[ScheduledEvent] = []

    def register_event(self, timestamp_ms: int, callback: Callable):
        self.events.append(ScheduledEvent(timestamp_ms, callback))

    def maybe_inject_event(self, current_time_ms: int):
        for event in self.events:
            if not event.executed and current_time_ms >= event.timestamp_ms:
                event.callback()
                event.executed = True

    def get_pending_events(self) -> List[Dict[str, Any]]:
        return [
            {
                "timestamp_ms": e.timestamp_ms,
                "executed": e.executed
            }
            for e in self.events
            if not e.executed
        ]
