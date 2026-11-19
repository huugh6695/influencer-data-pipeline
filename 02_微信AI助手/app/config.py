from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

def _get_csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]

def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8100
    db_path: str = "data/agent.db"
    admin_token: str = "change-me"
    channel: str = "mock"
    outbound_webhook_url: str = ""
    outbound_timeout: int = 15
    allowlist: list[str] = field(default_factory=list)
    quiet_hours: str = ""
    rate_limit_per_min: int = 6
    memory_window: int = 20
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_api_key: str = "ollama-local"
    llm_model: str = "qwen3.8:latest"
    llm_timeout: int = 120
    persona_name: str = "小鱼"
    persona_prompt: str = (
        "你是一个说话自然、简短、有分寸的 AI 聊天助手。"
        "必要时如实说明自己是 AI，不要长篇大论，不要使用 Markdown。"
    )

def load_settings(env_file: str | Path = ".env") -> Settings:
    _load_dotenv(Path(env_file))
    return Settings(
        host=os.getenv("HOST", "0.0.0.0"),
        port=_get_int("PORT", 8100),
        db_path=os.getenv("DB_PATH", "data/agent.db"),
        admin_token=os.getenv("ADMIN_TOKEN", "change-me"),
        channel=os.getenv("CHANNEL", "mock").strip().lower(),
        outbound_webhook_url=os.getenv("OUTBOUND_WEBHOOK_URL", "").strip(),
        outbound_timeout=_get_int("OUTBOUND_TIMEOUT", 15),
        allowlist=[item.lower() for item in _get_csv("ALLOWLIST")],
        quiet_hours=os.getenv("QUIET_HOURS", "").strip(),
        rate_limit_per_min=_get_int("RATE_LIMIT_PER_MIN", 6),
        memory_window=_get_int("MEMORY_WINDOW", 20),
        llm_base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/"),
        llm_api_key=os.getenv("LLM_API_KEY", "ollama-local"),
        llm_model=os.getenv("LLM_MODEL", "qwen3.8:latest"),
        llm_timeout=_get_int("LLM_TIMEOUT", 120),
        persona_name=os.getenv("PERSONA_NAME", "小鱼"),
        persona_prompt=os.getenv(
            "PERSONA_PROMPT",
            "你是一个说话自然、简短、有分寸的 AI 聊天助手。"
            "必要时如实说明自己是 AI，不要长篇大论，不要使用 Markdown。",
        ),
    )
