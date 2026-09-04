import uuid

import pytest

from app.queue import RunQueue


class FakePipeline:
    def __init__(self, counts: list[int]) -> None:
        self.counts = counts
        self.keys: list[str] = []

    def xlen(self, key: str) -> None:
        self.keys.append(key)

    async def execute(self) -> list[int]:
        return self.counts


class FakeRedis:
    def __init__(self, pipeline: FakePipeline) -> None:
        self._pipeline = pipeline

    def pipeline(self, transaction: bool = False) -> FakePipeline:
        assert transaction is False
        return self._pipeline


@pytest.mark.asyncio
async def test_logs_available_checks_all_run_streams_in_one_pipeline():
    run_ids = [uuid.uuid4(), uuid.uuid4()]
    pipeline = FakePipeline([0, 3])
    queue = RunQueue(FakeRedis(pipeline), ttl_seconds=60, log_stream_maxlen=100)  # type: ignore[arg-type]

    available = await queue.logs_available(run_ids)

    assert available == {run_ids[0]: False, run_ids[1]: True}
    assert pipeline.keys == [f"controller:run:{run_id}:logs" for run_id in run_ids]
