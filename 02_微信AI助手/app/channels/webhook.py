from __future__ import annotations

import logging

import httpx

from app.channels.base import Channel
from app.models import OutboundMessage

logger = logging.getLogger(__name__)

class WebhookChannel(Channel):
    name = "webhook"

    def __init__(self, url: str, timeout: int = 15) -> None:
        self.url = url
        self._client = httpx.AsyncClient(timeout=timeout)

    async def send(self, message: OutboundMessage) -> None:
        if not self.url:
            raise RuntimeError("OUTBOUND_WEBHOOK_URL is not configured")
        payload = message.model_dump()
        resp = await self._client.post(self.url, json=payload)
        resp.raise_for_status()
        logger.info(
            "sent via webhook conversation=%s status=%s",
            message.conversation_id,
            resp.status_code,
        )

    async def close(self) -> None:
        await self._client.aclose()
