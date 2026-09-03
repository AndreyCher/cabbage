from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .worker_config import ProxyGeoConfig, WorkerConfig


class RunCreate(BaseModel):
    identity: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    scenario: str = Field(min_length=1, max_length=128)
    priority: int = Field(default=0, ge=-100, le=100)
    debug: bool = False
    proxy_mode: Literal["default", "selected", "disabled"] = "default"
    proxy_config_id: uuid.UUID | None = None
    recording: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    worker_config: WorkerConfig = Field(default_factory=WorkerConfig)

    @model_validator(mode="after")
    def validate_proxy(self) -> "RunCreate":
        if self.proxy_mode == "selected" and self.proxy_config_id is None:
            raise ValueError("proxy_config_id is required for selected proxy mode")
        return self


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    identity: str
    status: str
    priority: int
    debug: bool
    proxy_mode: str
    current_stage: str | None
    current_action: int | None
    container_id: str | None
    error_reason: str | None
    artifact_path: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    scenario_name: str
    scenario_version: int
    live_stream_available: bool = False
    recorded_video_available: bool = False
    timeout_seconds: int | None = None
    worker_run_id: str | None = None
    worker_config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_run(cls, run: Any) -> "RunRead":
        return cls(
            **{
                name: getattr(run, name)
                for name in cls.model_fields
                if name not in {"scenario_name", "scenario_version", "live_stream_available", "recorded_video_available", "worker_config"}
            },
            scenario_name=run.scenario.name,
            scenario_version=run.scenario.version,
            worker_config=run.overrides or {},
        )


class RunUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=-100, le=100)
    status: Literal["queued", "cancelled"] | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    definition: dict[str, Any]
    default_proxy_config_id: uuid.UUID | None = None


class ScenarioClone(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: int
    definition: dict[str, Any]
    active: bool
    deleted: bool
    created_at: datetime
    run_count: int = 0
    default_proxy_config_id: uuid.UUID | None = None


class ProxyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scheme: Literal["http", "https"] = "http"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=4096)
    bypass: str | None = Field(default=None, max_length=4096)
    geoip: ProxyGeoConfig = Field(default_factory=ProxyGeoConfig)
    verify_ssl: bool = True


class ProxyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    scheme: Literal["http", "https"] | None = None
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=4096)
    bypass: str | None = Field(default=None, max_length=4096)
    geoip: ProxyGeoConfig | None = None
    verify_ssl: bool | None = None
    enabled: bool | None = None


class IdentityCreate(BaseModel):
    identity: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    config: WorkerConfig = Field(default_factory=WorkerConfig)
    default_proxy_config_id: uuid.UUID | None = None


class IdentityUpdate(BaseModel):
    config: WorkerConfig
    default_proxy_config_id: uuid.UUID | None = None


class IdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    identity: str
    config: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime
    in_use: bool = False
    pending_operation: str | None = None
    default_proxy_config_id: uuid.UUID | None = None


class IdentityDefaultsUpdate(BaseModel):
    config: WorkerConfig


class IdentityDefaultsRead(BaseModel):
    config: dict[str, Any]
    revision: int
    updated_at: datetime


class WorkerDefaultsUpdate(BaseModel):
    config: WorkerConfig


class WorkerDefaultsRead(BaseModel):
    config: dict[str, Any]
    revision: int
    updated_at: datetime
