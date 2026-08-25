from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunCreate(BaseModel):
    identity: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    scenario: str = Field(min_length=1, max_length=128)
    priority: int = Field(default=0, ge=-100, le=100)
    debug: bool = False
    proxy_mode: Literal["default", "selected", "disabled"] = "default"
    proxy_config_id: uuid.UUID | None = None
    recording: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    overrides: dict[str, Any] = Field(default_factory=dict)

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

    @classmethod
    def from_run(cls, run: Any) -> "RunRead":
        return cls(
            **{
                name: getattr(run, name)
                for name in cls.model_fields
                if name not in {"scenario_name", "scenario_version", "live_stream_available", "recorded_video_available"}
            },
            scenario_name=run.scenario.name,
            scenario_version=run.scenario.version,
        )


class RunUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=-100, le=100)
    status: Literal["queued", "cancelled"] | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    definition: dict[str, Any]


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


class ProxyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scheme: Literal["http", "https", "socks5"] = "http"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=4096)


class IdentityCreate(BaseModel):
    identity: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    config: dict[str, Any] = Field(default_factory=dict)


class IdentityUpdate(BaseModel):
    config: dict[str, Any]


class IdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    identity: str
    config: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime
    in_use: bool = False


class IdentityDefaultsUpdate(BaseModel):
    config: dict[str, Any]


class IdentityDefaultsRead(BaseModel):
    config: dict[str, Any]
    revision: int
    updated_at: datetime
