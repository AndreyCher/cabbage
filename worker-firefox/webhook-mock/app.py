import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Worker Webhook Mock")
CONFIG = Path("/config/profiles.json")

class ProfileRequest(BaseModel):
    id: str
    identity: str | None = None
    run_id: str | None = None

def load_profiles():
    with CONFIG.open("r", encoding="utf-8") as fh:
        return json.load(fh).get("profiles", {})

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/profile")
def profile(req: ProfileRequest):
    profiles = load_profiles()
    if req.id not in profiles:
        raise HTTPException(status_code=404, detail=f"profile not found: {req.id}")
    return profiles[req.id]
