from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages (channel, conversation_id, id);
"""

class MemoryStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def add(self, channel: str, conversation_id: str, role: str, content: str) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO messages (channel, conversation_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (channel, conversation_id, role, content, time.time()),
        )
        await self._db.commit()

    async def recent(
        self, channel: str, conversation_id: str, limit: int = 20
    ) -> list[dict[str, str]]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT role, content FROM messages"
            " WHERE channel = ? AND conversation_id = ?"
            " ORDER BY id DESC LIMIT ?",
            (channel, conversation_id, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    async def count(self) -> int:
        assert self._db is not None
        cursor = await self._db.execute("SELECT COUNT(*) FROM messages")
        row = await cursor.fetchone()
        await cursor.close()
        return int(row[0]) if row else 0
