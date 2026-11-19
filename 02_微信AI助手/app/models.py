from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class InboundMessage(BaseModel):
    account_id: str = ""
    conversation_id: str
    sender_id: str
    sender_name: str | None = None
    text: str = ""
    is_group: bool = False
    channel: str = "unknown"
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def conversation_key(self) -> str:
        return self.conversation_id.strip().lower()

class OutboundMessage(BaseModel):
    account_id: str = ""
    conversation_id: str
    text: str

class SendResult(BaseModel):
    ok: bool
    detail: str = ""
