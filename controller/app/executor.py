from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Protocol

import docker
from docker.models.containers import Container

from .settings import Settings


@dataclass(frozen=True)
class WorkerSpec:
    run_id: str
    identity: str
    config_path: str
    debug: bool


class Executor(Protocol):
    async def capacity(self) -> int: ...
    async def start(self, spec: WorkerSpec) -> str: ...
    async def inspect(self, container_id: str) -> dict: ...
    async def stop(self, container_id: str) -> None: ...
    async def remove(self, container_id: str) -> None: ...
    async def logs(self, container_id: str): ...
    async def internal_endpoint(self, container_id: str, port: int) -> str: ...


class DockerExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = docker.from_env()

    async def _call(self, function, *args, **kwargs):
        return await asyncio.to_thread(partial(function, *args, **kwargs))

    async def capacity(self) -> int:
        info = await self._call(self.client.info)
        total_memory_mb = int(info.get("MemTotal", 0)) // (1024 * 1024)
        total_cpus = float(info.get("NCPU", 1))
        memory_slots = max(0, int((total_memory_mb - self.settings.host_memory_reserve_mb) // self.settings.worker_memory_mb))
        cpu_slots = max(0, int((total_cpus - self.settings.host_cpu_reserve) // self.settings.worker_cpus))
        return min(self.settings.max_concurrent_runs, memory_slots, cpu_slots)

    async def start(self, spec: WorkerSpec) -> str:
        environment = {
            "WORKER_SYSTEM_CONFIG": spec.config_path,
            "WORKER_PROFILE": "run",
            "ENABLE_NOVNC": "true" if spec.debug else "false",
            "NOVNC_VIEW_ONLY": "true",
            "DISPLAY": ":99",
            "CAMOUFOX_EXECUTABLE_PATH": "/opt/camoufox-custom/camoufox-bin",
        }
        volumes = {
            self.settings.worker_config_volume: {"bind": "/controller-runs", "mode": "ro"},
            self.settings.identities_volume: {"bind": "/identities", "mode": "rw"},
            self.settings.artifacts_volume: {"bind": "/artifacts", "mode": "rw"},
        }
        container: Container = await self._call(
            self.client.containers.run,
            self.settings.worker_image,
            detach=True,
            name=f"worker-run-{spec.run_id}",
            network=self.settings.docker_network,
            environment=environment,
            volumes=volumes,
            mem_limit=f"{self.settings.worker_memory_mb}m",
            nano_cpus=int(self.settings.worker_cpus * 1_000_000_000),
            shm_size=f"{self.settings.worker_shm_size_mb}m",
            labels={"controller.run_id": spec.run_id, "controller.identity": spec.identity, "controller.host_id": self.settings.docker_host_id},
        )
        return container.id

    async def inspect(self, container_id: str) -> dict:
        container = await self._call(self.client.containers.get, container_id)
        await self._call(container.reload)
        return container.attrs

    async def internal_endpoint(self, container_id: str, port: int) -> str:
        attrs = await self.inspect(container_id)
        networks = attrs.get("NetworkSettings", {}).get("Networks", {})
        network = networks.get(self.settings.docker_network)
        if not network:
            network = next(iter(networks.values()), {})
        address = network.get("IPAddress")
        if not address:
            raise RuntimeError("worker_internal_address_unavailable")
        return f"{address}:{port}"

    async def stop(self, container_id: str) -> None:
        container = await self._call(self.client.containers.get, container_id)
        try:
            await self._call(container.kill, signal="SIGTERM")
            await asyncio.wait_for(self._wait(container), timeout=self.settings.stop_grace_seconds)
        except (asyncio.TimeoutError, docker.errors.APIError):
            try:
                await self._call(container.stop, timeout=self.settings.stop_kill_seconds)
            except docker.errors.APIError:
                await self._call(container.kill, signal="SIGKILL")

    async def _wait(self, container: Container) -> None:
        await self._call(container.wait)

    async def remove(self, container_id: str) -> None:
        container = await self._call(self.client.containers.get, container_id)
        await self._call(container.remove, force=True)

    async def log_lines(self, container_id: str) -> list[str]:
        container = await self._call(self.client.containers.get, container_id)
        data: bytes = await self._call(container.logs, stdout=True, stderr=True, timestamps=True)
        return data.decode(errors="replace").splitlines()
