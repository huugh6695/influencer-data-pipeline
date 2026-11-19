from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, time as dtime

from app.config import Settings
from app.models import InboundMessage

class Policy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._quiet = self._parse_quiet(settings.quiet_hours)

    @staticmethod
    def _parse_quiet(raw: str) -> tuple[dtime, dtime] | None:
        if not raw or "-" not in raw:
            return None
        start_raw, end_raw = raw.split("-", 1)
        try:
            start = datetime.strptime(start_raw.strip(), "%H:%M").time()
            end = datetime.strptime(end_raw.strip(), "%H:%M").time()
        except ValueError:
            return None
        return start, end

    def _in_quiet_hours(self, now: datetime) -> bool:
        if self._quiet is None:
            return False
        start, end = self._quiet
        current = now.time()
        if start <= end:
            return start <= current < end
        return current >= start or current < end

    def _rate_ok(self, key: str) -> bool:
        limit = self.settings.rate_limit_per_min
        if limit <= 0:
            return True
        now = time.monotonic()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def check(self, message: InboundMessage, now: datetime | None = None) -> tuple[bool, str]:
        key = message.conversation_key
        allowlist = set(self.settings.allowlist)
        if not allowlist:
            return False, "allowlist_empty"
        if key not in allowlist and message.sender_id.strip().lower() not in allowlist:
            return False, "not_allowlisted"
        if self._in_quiet_hours(now or datetime.now()):
            return False, "quiet_hours"
        if not self._rate_ok(key):
            return False, "rate_limited"
        return True, "ok"
