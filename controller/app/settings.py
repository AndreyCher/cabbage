from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTROLLER_", extra="ignore")

    database_url: str = "postgresql+asyncpg://controller:controller@postgres:5432/controller"
    redis_url: str = "redis://redis:6379/0"
    api_token_file: Path = Path("/run/secrets/controller_api_token")
    encryption_key_file: Path = Path("/run/secrets/controller_encryption_key")
    docker_host_id: str = "local"
    docker_network: str = "cabbage-internal"
    worker_image: str = "worker-firefox:latest"
    worker_config_root: Path = Path("/controller-runs")
    worker_config_volume: str = "cabbage-controller-runs"
    identities_volume: str = "cabbage-worker-identities"
    artifacts_volume: str = "cabbage-worker-artifacts"
    identities_root: Path = Path("/identities")
    artifacts_root: Path = Path("/artifacts")
    max_concurrent_runs: int = Field(default=4, ge=1)
    host_memory_reserve_mb: int = Field(default=2048, ge=0)
    host_cpu_reserve: float = Field(default=1.0, ge=0)
    worker_memory_mb: int = Field(default=2048, ge=256)
    worker_cpus: float = Field(default=1.0, gt=0)
    worker_shm_size_mb: int = Field(default=2048, ge=64)
    scheduler_interval_seconds: float = Field(default=2.0, gt=0)
    worker_startup_timeout_seconds: int = Field(default=120, ge=10, le=3600)
    worker_api_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    stop_grace_seconds: int = Field(default=30, ge=1)
    stop_kill_seconds: int = Field(default=15, ge=1)
    redis_ttl_seconds: int = Field(default=86400, ge=60)
    log_stream_maxlen: int = Field(default=5000, ge=100)
    stream_ticket_ttl_seconds: int = Field(default=300, ge=30, le=3600)

    def read_secret(self, path: Path, label: str) -> str:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Unable to read {label} file: {path}") from exc
        if not value:
            raise RuntimeError(f"{label} file is empty: {path}")
        return value

    @property
    def api_token(self) -> str:
        return self.read_secret(self.api_token_file, "API token")


@lru_cache
def get_settings() -> Settings:
    return Settings()
