from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .providers import DataResolver, JsonFileProvider


VERSION = (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip()
FILE_PATH = Path(os.getenv("DATA_PROVIDER_FILE_PATH", "/config/profiles.json"))
resolver = DataResolver([JsonFileProvider(FILE_PATH)])

app = FastAPI(title="Data Provider", version=VERSION)


class ProfileRequest(BaseModel):
    id: str
    identity: str | None = None
    run_id: str | None = None


class DataRequest(BaseModel):
    namespace: str
    key: str
    identity: str | None = None
    run_id: str | None = None


def resolve_data(namespace: str, key: str, identity: str | None, run_id: str | None):
    if not namespace or not key:
        raise HTTPException(status_code=400, detail="namespace and key are required")
    try:
        value, _provider = resolver.resolve(
            namespace,
            key,
            {"identity": identity, "run_id": run_id},
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"data backend unavailable: {exc}") from exc
    if value is None:
        raise HTTPException(status_code=404, detail=f"data not found: {namespace}/{key}")
    return value


def resolve_profile(request: ProfileRequest):
    return resolve_data("profiles", request.id, request.identity, request.run_id)


@app.get("/api/v1/health")
def health_v1():
    return {
        "status": "ok",
        "component": "data-provider",
        "version": VERSION,
        "providers": [provider.name for provider in resolver.providers],
    }


@app.get("/health")
def health_compatibility():
    return health_v1()


@app.post("/api/v1/profiles/resolve")
def profile_v1(request: ProfileRequest):
    return resolve_profile(request)


@app.post("/api/v1/data/resolve")
def data_v1(request: DataRequest):
    return resolve_data(request.namespace, request.key, request.identity, request.run_id)


@app.post("/api/profile")
def profile_compatibility(request: ProfileRequest):
    return resolve_profile(request)
