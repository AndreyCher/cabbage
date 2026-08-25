from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .models import Run, RunStatus
from .settings import Settings


def video_files(run: Run, settings: Settings) -> list[Path]:
    if not run.artifact_path:
        return []
    root = settings.artifacts_root.resolve()
    artifact = Path(run.artifact_path).resolve()
    if artifact != root and root not in artifact.parents:
        return []
    summary_path = artifact / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    controller_run_id = summary.get("controller_run_id")
    if controller_run_id:
        if controller_run_id != str(run.id):
            return []
    elif not _legacy_summary_matches_run(run, summary):
        return []
    recording = summary.get("recording") or {}
    recorded_names = {
        Path(str(filename)).name
        for filename in recording.get("files", [])
        if isinstance(filename, str) and filename.endswith(".webm")
    }
    if not recording.get("video") or not recorded_names:
        return []
    videos = artifact / "videos"
    if not videos.is_dir():
        return []
    return sorted(
        path for path in videos.glob("*.webm")
        if path.name in recorded_names and path.is_file() and path.stat().st_size > 0
    )


def _legacy_summary_matches_run(run: Run, summary: dict) -> bool:
    if summary.get("identity") != run.identity or summary.get("scenario") != run.scenario.name:
        return False
    if run.started_at is None:
        return False
    try:
        summary_started = datetime.fromisoformat(str(summary["started_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    run_started = run.started_at
    if run_started.tzinfo is None:
        run_started = run_started.replace(tzinfo=timezone.utc)
    return abs((summary_started - run_started).total_seconds()) <= 10


def live_stream_available(run: Run) -> bool:
    return bool(run.debug and run.container_id and run.status in {RunStatus.running.value, RunStatus.waiting_input.value})


async def create_stream_ticket(request: Request, run_id: uuid.UUID) -> str:
    ticket = secrets.token_urlsafe(32)
    ttl = request.app.state.settings.stream_ticket_ttl_seconds
    await request.app.state.redis.set(f"stream-ticket:{ticket}", str(run_id), ex=ttl)
    return ticket


async def validate_stream_ticket(app, ticket: str | None, run_id: uuid.UUID) -> bool:
    if not ticket:
        return False
    expected = await app.state.redis.get(f"stream-ticket:{ticket}")
    return bool(expected and secrets.compare_digest(expected, str(run_id)))


async def proxy_novnc_asset(request: Request, run: Run, asset_path: str, ticket: str | None) -> Response:
    if asset_path in {"", "vnc.html"} and not await validate_stream_ticket(request.app, ticket, run.id):
        raise HTTPException(401, detail="invalid_stream_ticket")
    if not live_stream_available(run):
        raise HTTPException(409, detail="live_stream_unavailable")
    if ".." in Path(asset_path).parts or asset_path.startswith("/"):
        raise HTTPException(400, detail="invalid_novnc_asset_path")
    endpoint = await request.app.state.executor.internal_endpoint(run.container_id, 6080)
    path = asset_path or "vnc.html"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"http://{endpoint}/{path}")
    headers = {}
    if content_type := response.headers.get("content-type"):
        headers["content-type"] = content_type
    if path == "vnc.html":
        headers["referrer-policy"] = "no-referrer"
    return Response(content=response.content, status_code=response.status_code, headers=headers)


async def proxy_novnc_websocket(websocket: WebSocket, run: Run, ticket: str | None) -> None:
    if not await validate_stream_ticket(websocket.app, ticket, run.id) or not live_stream_available(run):
        await websocket.close(code=1008)
        return
    try:
        endpoint = await websocket.app.state.executor.internal_endpoint(run.container_id, 6080)
        requested_protocols = websocket.headers.get("sec-websocket-protocol", "")
        protocol = "binary" if "binary" in requested_protocols.split(",") else None
        await websocket.accept(subprotocol=protocol)
        async with connect(f"ws://{endpoint}/websockify", subprotocols=["binary"] if protocol else None, max_size=None) as upstream:
            async def browser_to_worker() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("bytes") is not None:
                        await upstream.send(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream.send(message["text"])

            async def worker_to_browser() -> None:
                while True:
                    message = await upstream.recv()
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = {asyncio.create_task(browser_to_worker()), asyncio.create_task(worker_to_browser())}
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
    except (WebSocketDisconnect, ConnectionClosed, httpx.HTTPError, OSError, RuntimeError):
        pass


def recorded_video_response(run: Run, settings: Settings, filename: str) -> FileResponse:
    candidates = {path.name: path for path in video_files(run, settings)}
    path = candidates.get(filename)
    if path is None:
        raise HTTPException(404, detail="recorded_video_not_found")
    return FileResponse(path, media_type="video/webm", filename=path.name, content_disposition_type="inline")
