from __future__ import annotations

import logging
from datetime import datetime

from app.config import Settings
from app.core.llm import LLMClient
from app.core.memory import MemoryStore
from app.core.policy import Policy
from app.models import InboundMessage

logger = logging.getLogger(__name__)

class Agent:
    def __init__(
        self,
        settings: Settings,
        memory: MemoryStore,
        policy: Policy,
        llm: LLMClient,
    ) -> None:
        self.settings = settings
        self.memory = memory
        self.policy = policy
        self.llm = llm

    def _system_prompt(self) -> str:
        return (
            f"你的人设：{self.settings.persona_name}。\n"
            f"{self.settings.persona_prompt}\n"
            "规则：只输出要发到微信里的纯文本；不要加引号、不要加前缀、不要解释。"
        )

    # 入口: 策略 -> 记忆 -> 模型 -> 记忆
    async def handle(
        self, message: InboundMessage, now: datetime | None = None
    ) -> tuple[str | None, str]:
        allowed, reason = self.policy.check(message, now=now)
        if not allowed:
            logger.info(
                "skip conversation=%s reason=%s", message.conversation_id, reason
            )
            return None, reason

        text = message.text.strip()
        if not text:
            return None, "empty"

        await self.memory.add(
            message.channel, message.conversation_id, "user", text
        )
        history = await self.memory.recent(
            message.channel, message.conversation_id, self.settings.memory_window
        )
        messages = [{"role": "system", "content": self._system_prompt()}, *history]

        reply = await self.llm.chat(messages)
        reply = reply.strip()
        if not reply:
            return None, "empty_reply"

        await self.memory.add(
            message.channel, message.conversation_id, "assistant", reply
        )
        return reply, "ok"