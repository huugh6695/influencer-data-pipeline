from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque

from app.models import OutboundMessage

class Channel(ABC):

    name: str = "base"

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        return None

class MockChannel(Channel):

    name = "mock"

    def __init__(self, limit: int = 200) -> None:
        self.outbox: deque[OutboundMessage] = deque(maxlen=limit)

    async def send(self, message: OutboundMessage) -> None:
        self.outbox.append(message)

    def drain(self) -> list[OutboundMessage]:
        items = list(self.outbox)
        self.outbox.clear()
        return items
