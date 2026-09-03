from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from .api import router
from .executor import DockerExecutor
from .queue import RunQueue
from .scheduler import Scheduler
from .settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    queue = RunQueue(redis, settings.redis_ttl_seconds, settings.log_stream_maxlen)
    await queue.initialize()
    executor = DockerExecutor(settings)
    scheduler = Scheduler(settings, executor, queue)
    app.state.queue = queue
    app.state.redis = redis
    app.state.settings = settings
    app.state.executor = executor
    task = asyncio.create_task(scheduler.run_forever())
    yield
    scheduler.stop()
    await task
    await redis.aclose()


app = FastAPI(title="Controller API", version="0.1.14", lifespan=lifespan)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
