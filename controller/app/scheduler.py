from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select

from .database import SessionLocal
from .crypto import SecretCipher
from .executor import DockerExecutor, WorkerSpec
from .materializer import RunMaterializer
from .models import ACTIVE_STATUSES, IdentityProfile, Run, RunStatus, TERMINAL_STATUSES
from .queue import RunQueue
from .settings import Settings


def eligible_runs(queued_runs, active_identities: set[str], free_slots: int):
    """Select global priority/FIFO candidates while serializing each Identity."""
    selected = []
    reserved_identities = set(active_identities)
    for run in queued_runs:
        if len(selected) >= free_slots:
            break
        if run.identity in reserved_identities:
            continue
        selected.append(run)
        reserved_identities.add(run.identity)
    return selected


class Scheduler:
    def __init__(self, settings: Settings, executor: DockerExecutor, queue: RunQueue) -> None:
        self.settings = settings
        self.executor = executor
        self.queue = queue
        self.materializer = RunMaterializer(settings.worker_config_root)
        self.cipher = SecretCipher(settings)
        self._stop = asyncio.Event()
        self._log_offsets: dict[uuid.UUID, int] = {}

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception as exc:
                # The scheduler remains available after transient Docker/DB failures.
                print(f"scheduler tick failed: {exc}", flush=True)
            try:
                await asyncio.wait_for(self._stop.wait(), self.settings.scheduler_interval_seconds)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()

    async def tick(self) -> None:
        await self._monitor()
        capacity = await self.executor.capacity()
        async with SessionLocal() as session:
            active_count = await session.scalar(select(func.count()).select_from(Run).where(Run.status.in_([s.value for s in ACTIVE_STATUSES]))) or 0
            free_slots = max(0, capacity - active_count)
            if not free_slots:
                return
            active_identities = set((await session.scalars(
                select(Run.identity).where(Run.status.in_([s.value for s in ACTIVE_STATUSES]))
            )).all())
            result = await session.execute(
                select(Run).where(Run.status == RunStatus.queued.value)
                .order_by(Run.priority.desc(), Run.created_at.asc())
                .with_for_update(of=Run, skip_locked=True)
            )
            candidates = eligible_runs(result.scalars().unique(), active_identities, free_slots)
            for run in candidates:
                run.status = RunStatus.allocating.value
                run.controller_id = self.settings.docker_host_id
                await session.flush()
                try:
                    proxy = None
                    if run.proxy_mode == "selected" and run.proxy_config is not None:
                        proxy = {
                            "enabled": True,
                            "proxy_id": run.proxy_config.name,
                            "server": f"{run.proxy_config.scheme}://{run.proxy_config.host}:{run.proxy_config.port}",
                            "username": run.proxy_config.username,
                            "password": self.cipher.decrypt(run.proxy_config.encrypted_password) if run.proxy_config.encrypted_password else None,
                        }
                    identity_profile = await session.get(IdentityProfile, run.identity)
                    identity_config = identity_profile.config if identity_profile else {}
                    config_path = await asyncio.to_thread(
                        self.materializer.materialize, run, proxy, identity_config
                    )
                    container_id = await self.executor.start(WorkerSpec(str(run.id), run.identity, config_path, run.debug))
                    run.container_id = container_id
                    run.status = RunStatus.starting.value
                    run.started_at = datetime.now(timezone.utc)
                    run.current_stage = "container_starting"
                except Exception as exc:
                    run.status = RunStatus.failed.value
                    run.error_reason = f"container_start_failed: {exc}"
                    run.finished_at = datetime.now(timezone.utc)
            await session.commit()

    async def _monitor(self) -> None:
        async with SessionLocal() as session:
            result = await session.execute(select(Run).where(Run.container_id.is_not(None), Run.status.not_in([s.value for s in TERMINAL_STATUSES])))
            for run in result.scalars().unique():
                try:
                    state = (await self.executor.inspect(run.container_id))["State"]
                    docker_status = state.get("Status")
                    if docker_status == "running":
                        run.status = RunStatus.running.value
                        run.current_stage = "scenario_running"
                        try:
                            async with httpx.AsyncClient(timeout=1.5) as client:
                                response = await client.get(f"http://worker-run-{run.id}:8090/api/v1/identities/{run.identity}/runs/current")
                            if response.is_success:
                                worker_state = response.json()
                                worker_status = worker_state.get("status")
                                if worker_status in {"starting", "running", "waiting_input"}:
                                    run.status = worker_status
                                elif worker_status in {"completed", "failed", "stopped"}:
                                    # The worker may still be finalizing video and summary
                                    # files. The Docker exit code remains authoritative.
                                    run.status = RunStatus.running.value
                                    run.current_stage = "finalizing"
                                if worker_status == "failed" and worker_state.get("error_reason"):
                                    message = worker_state.get("error_message")
                                    run.error_reason = f"{worker_state['error_reason']}: {message}" if message else worker_state["error_reason"]
                                worker_run_id = worker_state.get("run_id")
                                if worker_run_id:
                                    run.artifact_path = f"/artifacts/{run.identity}/{run.scenario.name}/{worker_run_id}"
                                run.current_action = worker_state.get("current_action")
                                if worker_status not in {"completed", "failed", "stopped"}:
                                    run.current_stage = "waiting_input" if worker_status == "waiting_input" else (f"action_{run.current_action}" if run.current_action is not None else "scenario_running")
                        except httpx.HTTPError:
                            pass
                    elif docker_status in {"exited", "dead"}:
                        exit_code = int(state.get("ExitCode", 1))
                        run.status = RunStatus.completed.value if exit_code == 0 else RunStatus.failed.value
                        summary = await asyncio.to_thread(self._latest_summary, run)
                        if summary is not None:
                            run.artifact_path = str(summary["path"])
                            payload = summary["payload"]
                            if exit_code != 0:
                                reason = payload.get("reason") or f"worker_exit_code_{exit_code}"
                                message = payload.get("message") or payload.get("error")
                                run.error_reason = f"{reason}: {message}" if message else reason
                            run.current_action = payload.get("failed_action")
                        elif exit_code == 0:
                            run.error_reason = None
                        elif not run.error_reason:
                            run.error_reason = f"worker_exit_code_{exit_code}"
                        run.finished_at = datetime.now(timezone.utc)
                        run.current_stage = "finished"
                    lines = await self.executor.log_lines(run.container_id)
                    offset = self._log_offsets.get(run.id, 0)
                    for line in lines[offset:]:
                        await self.queue.append_log(run.id, "combined", line)
                    self._log_offsets[run.id] = len(lines)
                    await self.queue.live_state(run.id, {"status": run.status, "stage": run.current_stage, "container_id": run.container_id})
                except Exception as exc:
                    run.error_reason = f"container_inspect_failed: {exc}"
            await session.commit()

    def _latest_summary(self, run: Run) -> dict | None:
        scenario_root = self.settings.artifacts_root / run.identity / run.scenario.name
        candidates = list(scenario_root.glob("*/summary.json")) if scenario_root.is_dir() else []
        if not candidates:
            return None
        fallback = None
        for path in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if payload.get("controller_run_id") == str(run.id):
                return {"path": path.parent, "payload": payload}
            if not payload.get("controller_run_id") and fallback is None:
                try:
                    started = datetime.fromisoformat(str(payload["started_at"]).replace("Z", "+00:00"))
                    run_started = run.started_at
                    if run_started is not None and run_started.tzinfo is None:
                        run_started = run_started.replace(tzinfo=timezone.utc)
                    if run_started is not None and abs((started - run_started).total_seconds()) <= 10:
                        fallback = {"path": path.parent, "payload": payload}
                except (KeyError, TypeError, ValueError):
                    pass
        return fallback
