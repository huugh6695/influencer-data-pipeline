from __future__ import annotations

from app.channels.base import Channel, MockChannel
from app.channels.webhook import WebhookChannel
from app.config import Settings

def build_channel(settings: Settings) -> Channel:
    if settings.channel == "mock":
        return MockChannel()
    if settings.channel == "webhook":
        return WebhookChannel(settings.outbound_webhook_url, settings.outbound_timeout)
    raise ValueError(f"unknown channel: {settings.channel}")
