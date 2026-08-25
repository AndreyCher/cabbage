from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import require_token
from .crypto import SecretCipher
from .database import SessionLocal, session_dependency
from .executor import DockerExecutor
from .models import ACTIVE_STATUSES, ControllerSetting, IdentityProfile, ProxyConfig, Run, RunStatus, ScenarioTemplate, TERMINAL_STATUSES
from .queue import RunQueue
from .schemas import IdentityCreate, IdentityDefaultsRead, IdentityDefaultsUpdate, IdentityRead, IdentityUpdate, ProxyCreate, RunCreate, RunRead, RunUpdate, ScenarioClone, ScenarioCreate, ScenarioRead
from .settings import get_settings
from .streaming import create_stream_ticket, live_stream_available, proxy_novnc_asset, proxy_novnc_websocket, recorded_video_response, validate_stream_ticket, video_files

router = APIRouter(prefix="/api/v1")


def services(request):
    return request.app.state.queue, request.app.state.executor


def run_read(run: Run) -> RunRead:
    settings = get_settings()
    return RunRead.from_run(run).model_copy(update={
        "live_stream_available": live_stream_available(run),
        "recorded_video_available": bool(video_files(run, settings)),
    })


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "component": "controller", "version": "0.1.12", "api_version": "v1"}


@router.get("/runs", response_model=list[RunRead], dependencies=[Depends(require_token)])
async def list_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=500, ge=1, le=10000),
    session: AsyncSession = Depends(session_dependency),
) -> list[RunRead]:
    query = select(Run).order_by(Run.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(Run.status == status_filter)
    result = await session.execute(query)
    return [run_read(run) for run in result.scalars().unique()]


@router.post("/runs", response_model=RunRead, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_token)])
async def create_run(payload: RunCreate, request: Request, session: AsyncSession = Depends(session_dependency)) -> RunRead:
    scenario = await session.scalar(select(ScenarioTemplate).where(ScenarioTemplate.name == payload.scenario, ScenarioTemplate.active.is_(True)).order_by(ScenarioTemplate.version.desc()).limit(1))
    if scenario is None:
        raise HTTPException(404, detail="scenario_not_found")
    if await session.get(IdentityProfile, payload.identity) is None:
        raise HTTPException(404, detail={"code": "identity_not_found", "identity": payload.identity, "suggestion": "create_identity"})
    overrides = dict(payload.overrides)
    if payload.recording is not None:
        overrides.setdefault("recording", {})["video"] = payload.recording
    if payload.timeout_seconds is not None:
        overrides.setdefault("run", {})["timeout_seconds"] = payload.timeout_seconds
    run = Run(identity=payload.identity, scenario=scenario, proxy_config_id=payload.proxy_config_id, status=RunStatus.queued.value, priority=payload.priority, debug=payload.debug, proxy_mode=payload.proxy_mode, overrides=overrides)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await request.app.state.queue.enqueue(run.id, run.priority)
    return run_read(run)


@router.get("/runs/{run_id}", response_model=RunRead, dependencies=[Depends(require_token)])
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(session_dependency)) -> RunRead:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    return run_read(run)


@router.patch("/runs/{run_id}", response_model=RunRead, dependencies=[Depends(require_token)])
async def update_run(run_id: uuid.UUID, payload: RunUpdate, session: AsyncSession = Depends(session_dependency)) -> RunRead:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    if payload.priority is not None:
        if run.status != RunStatus.queued.value:
            raise HTTPException(409, detail="priority_only_available_for_queued_runs")
        run.priority = payload.priority
    if payload.status == "cancelled":
        if run.status != RunStatus.queued.value:
            raise HTTPException(409, detail="only_queued_runs_can_be_cancelled")
        run.status = RunStatus.cancelled.value
        run.finished_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(run)
    return run_read(run)


@router.post("/runs/{run_id}/stop", response_model=RunRead, dependencies=[Depends(require_token)])
async def stop_run(run_id: uuid.UUID, request: Request, session: AsyncSession = Depends(session_dependency)) -> RunRead:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    if run.status == RunStatus.queued.value:
        run.status = RunStatus.cancelled.value
    elif run.status in [s.value for s in TERMINAL_STATUSES]:
        raise HTTPException(409, detail="run_already_finished")
    else:
        run.status = RunStatus.stopping.value
        await session.commit()
        if run.container_id:
            await request.app.state.executor.stop(run.container_id)
        run.status = RunStatus.stopped.value
    run.finished_at = datetime.now(timezone.utc)
    run.current_stage = "stopped"
    await session.commit()
    await session.refresh(run)
    return run_read(run)


@router.get("/runs/{run_id}/logs", dependencies=[Depends(require_token)])
async def get_logs(run_id: uuid.UUID, request: Request, after: str = "-", count: int = Query(default=500, ge=1, le=5000)):
    return await request.app.state.queue.logs(run_id, after, count)


@router.get("/runs/{run_id}/logs/stream", dependencies=[Depends(require_token)])
async def stream_logs(run_id: uuid.UUID, request: Request):
    async def events():
        cursor = "0-0"
        while True:
            rows = await request.app.state.queue.logs(run_id, cursor, 200)
            for row in rows:
                cursor = row["id"]
                yield f"data: {json.dumps(row)}\n\n"
            if await request.is_disconnected():
                break
            await asyncio.sleep(1)
    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/runs/{run_id}/stream-ticket", dependencies=[Depends(require_token)])
async def issue_stream_ticket(run_id: uuid.UUID, request: Request, session: AsyncSession = Depends(session_dependency)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    if not live_stream_available(run) and not video_files(run, get_settings()):
        raise HTTPException(409, detail="run_stream_media_unavailable")
    return {
        "ticket": await create_stream_ticket(request, run_id),
        "expires_in": get_settings().stream_ticket_ttl_seconds,
    }


@router.get("/runs/{run_id}/media", dependencies=[Depends(require_token)])
async def get_run_media(run_id: uuid.UUID, session: AsyncSession = Depends(session_dependency)):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    files = video_files(run, get_settings())
    return {
        "live": live_stream_available(run),
        "videos": [{"name": path.name, "size": path.stat().st_size} for path in files],
    }


@router.get("/runs/{run_id}/novnc/{asset_path:path}")
async def get_novnc_asset(
    run_id: uuid.UUID,
    asset_path: str,
    request: Request,
    ticket: str | None = None,
    session: AsyncSession = Depends(session_dependency),
):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    return await proxy_novnc_asset(request, run, asset_path, ticket)


@router.websocket("/runs/{run_id}/novnc/websockify")
async def novnc_websocket(websocket: WebSocket, run_id: uuid.UUID, ticket: str | None = None):
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            await websocket.close(code=1008)
            return
        await proxy_novnc_websocket(websocket, run, ticket)


@router.get("/runs/{run_id}/videos/{filename}")
async def get_recorded_video(
    run_id: uuid.UUID,
    filename: str,
    request: Request,
    ticket: str | None = None,
    session: AsyncSession = Depends(session_dependency),
):
    if not await validate_stream_ticket(request.app, ticket, run_id):
        raise HTTPException(401, detail="invalid_stream_ticket")
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, detail="run_not_found")
    return recorded_video_response(run, get_settings(), filename)


@router.get("/identities", response_model=list[IdentityRead], dependencies=[Depends(require_token)])
async def list_identities(session: AsyncSession = Depends(session_dependency)):
    rows = (await session.scalars(select(IdentityProfile).order_by(IdentityProfile.identity))).all()
    active = set((await session.scalars(select(Run.identity).where(Run.status.in_([s.value for s in ACTIVE_STATUSES])))).all())
    return [IdentityRead.model_validate(row).model_copy(update={"in_use": row.identity in active}) for row in rows]


@router.post("/identities", response_model=IdentityRead, status_code=201, dependencies=[Depends(require_token)])
async def create_identity(payload: IdentityCreate, session: AsyncSession = Depends(session_dependency)):
    if await session.get(IdentityProfile, payload.identity):
        raise HTTPException(409, detail="identity_exists")
    defaults = await session.get(ControllerSetting, "identity_defaults")
    config = _deep_merge(defaults.value if defaults else {}, payload.config)
    row = IdentityProfile(identity=payload.identity, config=config)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/identities/{identity}", response_model=IdentityRead, dependencies=[Depends(require_token)])
async def get_identity(identity: str, session: AsyncSession = Depends(session_dependency)):
    row = await session.get(IdentityProfile, identity)
    if row is None:
        raise HTTPException(404, detail="identity_not_found")
    in_use = bool(await session.scalar(select(func.count()).select_from(Run).where(Run.identity == identity, Run.status.in_([s.value for s in ACTIVE_STATUSES]))))
    return IdentityRead.model_validate(row).model_copy(update={"in_use": in_use})


@router.put("/identities/{identity}", response_model=IdentityRead, dependencies=[Depends(require_token)])
async def update_identity(identity: str, payload: IdentityUpdate, session: AsyncSession = Depends(session_dependency)):
    row = await session.get(IdentityProfile, identity)
    if row is None:
        raise HTTPException(404, detail="identity_not_found")
    row.config = payload.config
    row.revision += 1
    await session.commit()
    await session.refresh(row)
    return row


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@router.delete("/identities/{identity}", status_code=204, dependencies=[Depends(require_token)])
async def delete_identity(
    identity: str,
    delete_account_data: bool = False,
    session: AsyncSession = Depends(session_dependency),
):
    row = await session.get(IdentityProfile, identity)
    if row is None:
        raise HTTPException(404, detail="identity_not_found")
    in_use = bool(await session.scalar(select(func.count()).select_from(Run).where(Run.identity == identity, Run.status.in_([s.value for s in ACTIVE_STATUSES]))))
    if in_use:
        raise HTTPException(409, detail="identity_in_use")
    if delete_account_data:
        root = get_settings().identities_root.resolve()
        target = root / identity
        if target.parent.resolve() != root or target.is_symlink():
            raise HTTPException(400, detail="unsafe_identity_path")
        if target.exists():
            await asyncio.to_thread(shutil.rmtree, target)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)


@router.get("/settings/identity-defaults", response_model=IdentityDefaultsRead, dependencies=[Depends(require_token)])
async def get_identity_defaults(session: AsyncSession = Depends(session_dependency)):
    row = await session.get(ControllerSetting, "identity_defaults")
    if row is None:
        raise HTTPException(404, detail="identity_defaults_not_found")
    return {"config": row.value, "revision": row.revision, "updated_at": row.updated_at}


@router.put("/settings/identity-defaults", response_model=IdentityDefaultsRead, dependencies=[Depends(require_token)])
async def update_identity_defaults(payload: IdentityDefaultsUpdate, session: AsyncSession = Depends(session_dependency)):
    row = await session.get(ControllerSetting, "identity_defaults")
    if row is None:
        row = ControllerSetting(key="identity_defaults", value=payload.config)
        session.add(row)
    else:
        row.value = payload.config
        row.revision += 1
    await session.commit()
    await session.refresh(row)
    return {"config": row.value, "revision": row.revision, "updated_at": row.updated_at}


@router.get("/scenarios", response_model=list[ScenarioRead], dependencies=[Depends(require_token)])
async def list_scenarios(include_archived: bool = False, session: AsyncSession = Depends(session_dependency)):
    query = (
        select(ScenarioTemplate, func.count(Run.id).label("run_count"))
        .outerjoin(Run, Run.scenario_id == ScenarioTemplate.id)
        .where(ScenarioTemplate.deleted.is_(False))
        .group_by(ScenarioTemplate.id)
        .order_by(ScenarioTemplate.name, ScenarioTemplate.version.desc())
    )
    if not include_archived:
        query = query.where(ScenarioTemplate.active.is_(True))
    result = await session.execute(query)
    return [ScenarioRead.model_validate(scenario).model_copy(update={"run_count": run_count}) for scenario, run_count in result.all()]


@router.delete("/scenarios/{name}", status_code=204, dependencies=[Depends(require_token)])
async def delete_scenario(name: str, session: AsyncSession = Depends(session_dependency)):
    rows = (await session.scalars(select(ScenarioTemplate).where(ScenarioTemplate.name == name, ScenarioTemplate.deleted.is_(False)))).all()
    if not rows:
        raise HTTPException(404, detail="scenario_not_found")
    for row in rows:
        row.active = False
        row.deleted = True
    await session.commit()
    return Response(status_code=204)


@router.post("/scenarios/versions/{scenario_id}/activate", response_model=ScenarioRead, dependencies=[Depends(require_token)])
async def activate_scenario_version(scenario_id: uuid.UUID, session: AsyncSession = Depends(session_dependency)):
    selected = await session.get(ScenarioTemplate, scenario_id)
    if selected is None or selected.deleted:
        raise HTTPException(404, detail="scenario_version_not_found")
    rows = (await session.scalars(select(ScenarioTemplate).where(ScenarioTemplate.name == selected.name, ScenarioTemplate.deleted.is_(False)).with_for_update())).all()
    for row in rows:
        row.active = row.id == selected.id
    await session.commit()
    await session.refresh(selected)
    return selected


@router.post("/scenarios/versions/{scenario_id}/clone", response_model=ScenarioRead, status_code=201, dependencies=[Depends(require_token)])
async def clone_scenario_version(scenario_id: uuid.UUID, payload: ScenarioClone, session: AsyncSession = Depends(session_dependency)):
    source = await session.get(ScenarioTemplate, scenario_id)
    if source is None or source.deleted:
        raise HTTPException(404, detail="scenario_version_not_found")
    if await session.scalar(select(func.count()).select_from(ScenarioTemplate).where(ScenarioTemplate.name == payload.name)):
        raise HTTPException(409, detail="scenario_name_exists")
    definition = dict(source.definition)
    definition["name"] = payload.name
    definition["version"] = 1
    scenario = ScenarioTemplate(name=payload.name, version=1, definition=definition, active=True, deleted=False)
    session.add(scenario)
    await session.commit()
    await session.refresh(scenario)
    return scenario


@router.post("/scenarios", response_model=ScenarioRead, status_code=201, dependencies=[Depends(require_token)])
async def create_scenario(payload: ScenarioCreate, session: AsyncSession = Depends(session_dependency)):
    actions = payload.definition.get("actions")
    if not isinstance(actions, list):
        raise HTTPException(422, detail="scenario_actions_must_be_array")
    definition = dict(payload.definition)
    definition["name"] = payload.name
    version = (await session.scalar(select(func.max(ScenarioTemplate.version)).where(ScenarioTemplate.name == payload.name)) or 0) + 1
    for current in (await session.scalars(select(ScenarioTemplate).where(ScenarioTemplate.name == payload.name, ScenarioTemplate.active.is_(True)))).all():
        current.active = False
    definition["version"] = version
    scenario = ScenarioTemplate(name=payload.name, version=version, definition=definition)
    session.add(scenario)
    await session.commit()
    await session.refresh(scenario)
    return scenario


@router.get("/proxies", dependencies=[Depends(require_token)])
async def list_proxies(session: AsyncSession = Depends(session_dependency)):
    result = await session.execute(select(ProxyConfig).where(ProxyConfig.enabled.is_(True)).order_by(ProxyConfig.name))
    return [{"id": row.id, "name": row.name, "scheme": row.scheme, "host": row.host, "port": row.port, "username": row.username, "has_password": bool(row.encrypted_password)} for row in result.scalars()]


@router.post("/proxies", status_code=201, dependencies=[Depends(require_token)])
async def create_proxy(payload: ProxyCreate, session: AsyncSession = Depends(session_dependency)):
    if await session.scalar(select(ProxyConfig).where(ProxyConfig.name == payload.name)):
        raise HTTPException(409, detail="proxy_name_exists")
    cipher = SecretCipher(get_settings())
    row = ProxyConfig(name=payload.name, scheme=payload.scheme, host=payload.host, port=payload.port, username=payload.username, encrypted_password=cipher.encrypt(payload.password) if payload.password else None)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {"id": row.id, "name": row.name, "scheme": row.scheme, "host": row.host, "port": row.port, "username": row.username, "has_password": bool(row.encrypted_password)}
