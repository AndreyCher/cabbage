from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis


QUEUE_STREAM = "controller:runs:queue"
QUEUE_GROUP = "controller-schedulers"


class RunQueue:
    def __init__(self, redis: Redis, ttl_seconds: int, log_stream_maxlen: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.log_stream_maxlen = log_stream_maxlen

    async def initialize(self) -> None:
        try:
            await self.redis.xgroup_create(QUEUE_STREAM, QUEUE_GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, run_id: uuid.UUID, priority: int) -> str:
        return await self.redis.xadd(QUEUE_STREAM, {"run_id": str(run_id), "priority": priority})

    async def live_state(self, run_id: uuid.UUID, values: dict[str, Any]) -> None:
        key = f"controller:run:{run_id}:state"
        encoded = {name: json.dumps(value) for name, value in values.items() if value is not None}
        if encoded:
            await self.redis.hset(key, mapping=encoded)
            await self.redis.expire(key, self.ttl_seconds)

    async def append_log(self, run_id: uuid.UUID, stream: str, message: str) -> None:
        key = f"controller:run:{run_id}:logs"
        await self.redis.xadd(key, {"stream": stream, "message": message}, maxlen=self.log_stream_maxlen, approximate=True)
        await self.redis.expire(key, self.ttl_seconds)

    async def logs(self, run_id: uuid.UUID, after: str = "-", count: int = 500) -> list[dict[str, str]]:
        minimum = after if after == "-" else f"({after}"
        rows = await self.redis.xrange(f"controller:run:{run_id}:logs", min=minimum, max="+", count=count)
        return [{"id": row_id, **fields} for row_id, fields in rows]
