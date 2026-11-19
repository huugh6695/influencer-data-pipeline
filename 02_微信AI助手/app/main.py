from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from app.channels import build_channel
from app.config import Settings, load_settings
from app.core.agent import Agent
from app.core.llm import LLMClient
from app.core.memory import MemoryStore
from app.core.policy import Policy
from app.models import InboundMessage, OutboundMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("wechat-agent")

class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory = MemoryStore(settings.db_path)
        self.policy = Policy(settings)
        self.llm = LLMClient(settings)
        self.channel = build_channel(settings)
        self.agent = Agent(settings, self.memory, self.policy, self.llm)

    async def start(self) -> None:
        await self.memory.connect()

    async def stop(self) -> None:
        await self.llm.close()
        await self.channel.close()
        await self.memory.close()

# 入口: create_app 装配 Runtime
def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = Runtime(settings or load_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        logger.info(
            "started channel=%s allowlist=%d",
            runtime.settings.channel,
            len(runtime.settings.allowlist),
        )
        yield
        await runtime.stop()

    app = FastAPI(title="wechat-agent", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime

    def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
        if x_admin_token != runtime.settings.admin_token:
            raise HTTPException(status_code=401, detail="invalid admin token")

    def normalize(payload: dict[str, Any], channel_name: str) -> InboundMessage:
        conversation_id = (
            payload.get("conversation_id")
            or payload.get("room_id")
            or payload.get("from")
            or payload.get("wxid")
            or ""
        )
        sender_id = payload.get("sender_id") or payload.get("from") or conversation_id
        text = payload.get("text")
        if text is None:
            text = payload.get("content", "")
        return InboundMessage(
            account_id=str(payload.get("account_id", "")),
            conversation_id=str(conversation_id),
            sender_id=str(sender_id),
            sender_name=payload.get("sender_name"),
            text=str(text),
            is_group=bool(payload.get("is_group", False)),
            channel=channel_name,
            raw=payload,
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "channel": runtime.settings.channel,
            "allowlist": len(runtime.settings.allowlist),
            "messages": await runtime.memory.count(),
        }

    # 入口: 渠道回调
    @app.post("/webhook/{channel_name}")
    async def webhook(channel_name: str, request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="invalid json")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be an object")

        message = normalize(payload, channel_name)
        if not message.conversation_id:
            raise HTTPException(status_code=400, detail="conversation_id required")

        reply, reason = await runtime.agent.handle(message)
        if reply is not None:
            # 出口: 统一走渠道发送
            await runtime.channel.send(
                OutboundMessage(
                    account_id=message.account_id,
                    conversation_id=message.conversation_id,
                    text=reply,
                )
            )
        return {"ok": True, "replied": reply is not None, "reason": reason}

    @app.post("/api/send", dependencies=[Depends(require_admin)])
    async def send(payload: dict[str, Any]) -> dict[str, Any]:
        conversation_id = str(payload.get("conversation_id", ""))
        text = str(payload.get("text", ""))
        if not conversation_id or not text:
            raise HTTPException(status_code=400, detail="conversation_id and text required")
        await runtime.channel.send(
            OutboundMessage(
                account_id=str(payload.get("account_id", "")),
                conversation_id=conversation_id,
                text=text,
            )
        )
        return {"ok": True}

    @app.get("/api/outbox", dependencies=[Depends(require_admin)])
    async def outbox() -> dict[str, Any]:
        drain = getattr(runtime.channel, "drain", None)
        items = drain() if callable(drain) else []
        return {"items": [item.model_dump() for item in items]}

    return app

app = create_app()
