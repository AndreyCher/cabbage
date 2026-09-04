from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    queued = "queued"
    allocating = "allocating"
    starting = "starting"
    running = "running"
    waiting_input = "waiting_input"
    completed = "completed"
    failed = "failed"
    stopping = "stopping"
    stopped = "stopped"
    cancelled = "cancelled"


ACTIVE_STATUSES = {
    RunStatus.allocating, RunStatus.starting, RunStatus.running,
    RunStatus.waiting_input, RunStatus.stopping,
}
TERMINAL_STATUSES = {RunStatus.completed, RunStatus.failed, RunStatus.stopped, RunStatus.cancelled}


class ScenarioTemplate(Base):
    __tablename__ = "scenario_templates"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProxyConfig(Base):
    __tablename__ = "proxy_configs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    scheme: Mapped[str] = mapped_column(String(16), default="http")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str | None] = mapped_column(String(255))
    encrypted_password: Mapped[str | None] = mapped_column(Text)
    bypass: Mapped[str | None] = mapped_column(Text)
    geoip: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    expected_country_code: Mapped[str | None] = mapped_column(String(2))
    country_name: Mapped[str | None] = mapped_column(String(128))
    exit_ip: Mapped[str | None] = mapped_column(String(64))
    timezone: Mapped[str | None] = mapped_column(String(128))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    check_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    check_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class ProxyCheckJob(Base):
    __tablename__ = "proxy_check_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proxy_config_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proxy_configs.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    requested_by: Mapped[str] = mapped_column(String(32), default="scheduler")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class ProxyCheckResult(Base):
    __tablename__ = "proxy_check_results"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proxy_check_jobs.id"), index=True)
    proxy_config_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proxy_configs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    exit_ip: Mapped[str | None] = mapped_column(String(64))
    country_code: Mapped[str | None] = mapped_column(String(2))
    country_name: Mapped[str | None] = mapped_column(String(128))
    timezone: Mapped[str | None] = mapped_column(String(128))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdentityProfile(Base):
    __tablename__ = "identity_profiles"
    identity: Mapped[str] = mapped_column(String(128), primary_key=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    pending_operation: Mapped[str | None] = mapped_column(String(16))
    proxy_country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ControllerSetting(Base):
    __tablename__ = "controller_settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity: Mapped[str] = mapped_column(String(128), index=True)
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario_templates.id"))
    proxy_config_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proxy_configs.id"))
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.queued.value, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    debug: Mapped[bool] = mapped_column(Boolean, default=False)
    proxy_mode: Mapped[str] = mapped_column(String(16), default="default")
    ignore_identity_location: Mapped[bool] = mapped_column(Boolean, default=False)
    ignore_proxy_requirement: Mapped[bool] = mapped_column(Boolean, default=False)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    worker_run_id: Mapped[str | None] = mapped_column(String(64))
    current_stage: Mapped[str | None] = mapped_column(String(255))
    current_action: Mapped[int | None] = mapped_column(Integer)
    container_id: Mapped[str | None] = mapped_column(String(128), index=True)
    controller_id: Mapped[str | None] = mapped_column(String(128), index=True)
    error_reason: Mapped[str | None] = mapped_column(Text)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scenario: Mapped[ScenarioTemplate] = relationship(lazy="joined")
    proxy_config: Mapped[ProxyConfig | None] = relationship(lazy="joined")
