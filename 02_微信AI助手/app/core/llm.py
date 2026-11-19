from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

class LLMError(RuntimeError):
    pass

class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=settings.llm_timeout,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )

    async def chat(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.settings.llm_base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 512,
            "stream": False,
        }
        resp = await self._client.post(url, json=payload)
        if resp.status_code >= 400:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected LLM response: {str(data)[:300]}") from exc

    async def close(self) -> None:
        await self._client.aclose()
