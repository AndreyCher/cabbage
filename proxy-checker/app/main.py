from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from cryptography.fernet import Fernet
from fastapi import FastAPI

VERSION = "0.1.1"
_container_config = Path("/app/config.json")
DEFAULT_CONFIG_PATH = Path(os.getenv("PROXY_CHECKER_CONFIG_PATH", str(_container_config if _container_config.exists() else Path(__file__).parents[1] / "config.json")))
DATABASE_URL = os.getenv("PROXY_CHECKER_DATABASE_URL", "postgresql://controller:controller@postgres:5432/controller").replace("postgresql+asyncpg://", "postgresql://")
KEY_FILE = Path(os.getenv("PROXY_CHECKER_ENCRYPTION_KEY_FILE", "/run/secrets/controller_encryption_key"))


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        result[key] = deep_merge(result.get(key, {}), value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def normalize(provider: str, data: dict) -> dict:
    if provider == "ipwhois":
        if data.get("success") is False: raise ValueError(data.get("message") or "lookup failed")
        timezone = data.get("timezone") or {}
        result = {"exit_ip": data.get("ip"), "country_code": data.get("country_code"), "country_name": data.get("country"), "timezone": timezone.get("id") if isinstance(timezone, dict) else timezone}
    elif provider == "freeipapi":
        result = {"exit_ip": data.get("ipAddress") or data.get("ip_address"), "country_code": data.get("countryCode") or data.get("country_code"), "country_name": data.get("countryName") or data.get("country_name"), "timezone": data.get("timeZone") or data.get("timezone")}
    elif provider == "ipapi_co":
        if data.get("error"): raise ValueError(data.get("message") or data.get("reason") or "lookup failed")
        result = {"exit_ip": data.get("ip"), "country_code": data.get("country_code"), "country_name": data.get("country_name"), "timezone": data.get("timezone")}
    else:
        result = {"exit_ip": data.get("ip"), "country_code": data.get("country_code"), "country_name": data.get("country_name"), "timezone": data.get("timezone")}
    if not result["exit_ip"] or not result["country_code"] or not result["timezone"]: raise ValueError("provider response lacks IP, country code or timezone")
    result["country_code"] = str(result["country_code"]).upper()
    return result


class Checker:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None
        self.running = True
        self.active = 0
        self.last_cycle: float | None = None
        self.last_error: str | None = None
        self.local = json.loads(DEFAULT_CONFIG_PATH.read_text())
        self.cipher: Fernet | None = None

    async def settings(self) -> dict:
        async with self.pool.acquire() as conn:
            value = await conn.fetchval("SELECT value FROM controller_settings WHERE key='proxy_checker'")
        if isinstance(value, str): value = json.loads(value)
        return deep_merge(self.local, dict(value or {}))

    async def enqueue_due(self, cfg: dict) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE proxy_configs SET check_status='pending' WHERE enabled AND check_status='healthy' AND last_checked_at < now() - make_interval(secs => $1::double precision)", cfg["stale_after_seconds"])
            await conn.execute("""
                INSERT INTO proxy_check_jobs (id, proxy_config_id, priority, status, requested_by)
                SELECT gen_random_uuid(), p.id, 0, 'queued', 'scheduler' FROM proxy_configs p
                WHERE p.enabled AND NOT EXISTS (SELECT 1 FROM proxy_check_jobs j WHERE j.proxy_config_id=p.id AND j.status IN ('queued','running'))
                AND (p.last_checked_at IS NULL OR p.last_checked_at < now() - make_interval(secs => CASE WHEN p.check_status='healthy' THEN $1::double precision ELSE $2::double precision END))
            """, cfg["check_interval_seconds"], cfg["unhealthy_retry_seconds"])

    async def claim(self) -> dict | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT * FROM proxy_check_jobs WHERE status='queued' ORDER BY priority DESC, created_at FOR UPDATE SKIP LOCKED LIMIT 1")
                if not row: return None
                await conn.execute("UPDATE proxy_check_jobs SET status='running', started_at=now() WHERE id=$1", row["id"])
                proxy = await conn.fetchrow("SELECT * FROM proxy_configs WHERE id=$1", row["proxy_config_id"])
                return {"job": dict(row), "proxy": dict(proxy)}

    async def provider_call(self, name: str, provider_cfg: dict, proxy: dict, timeout: int) -> tuple[dict, int]:
        password = self.cipher.decrypt(proxy["encrypted_password"].encode()).decode() if proxy["encrypted_password"] else None
        proxy_url = httpx.URL(f'{proxy["scheme"]}://{proxy["host"]}:{proxy["port"]}', username=proxy["username"], password=password)
        headers = {}
        secret_file = provider_cfg.get("token_secret_file")
        if secret_file: headers["Authorization"] = f"Bearer {Path(secret_file).read_text().strip()}"
        started = time.monotonic()
        async with httpx.AsyncClient(proxy=proxy_url, verify=proxy["verify_ssl"], timeout=timeout) as client:
            response = await client.get(provider_cfg["url"], headers=headers); response.raise_for_status(); data = response.json()
        return normalize(name, data), round((time.monotonic() - started) * 1000)

    async def check(self, item: dict, cfg: dict) -> None:
        job, proxy = item["job"], item["proxy"]
        attempts: list[tuple[str, bool, dict | None, int | None, str | None]] = []
        accepted = None
        countries: dict[str, int] = {}
        expected = proxy["expected_country_code"] or proxy["country_code"]
        for name in cfg["providers"]:
            pcfg = cfg["provider_config"].get(name, {})
            if not pcfg.get("enabled") or not pcfg.get("url"): continue
            for attempt in range(cfg["retries"] + 1):
                try:
                    result, latency = await self.provider_call(name, pcfg, proxy, cfg["timeout_seconds"])
                    attempts.append((name, True, result, latency, None)); countries[result["country_code"]] = countries.get(result["country_code"], 0) + 1
                    if not expected or result["country_code"] == expected: accepted = result
                    elif countries[result["country_code"]] >= 2: accepted = result
                    break
                except Exception as exc:
                    if attempt == cfg["retries"]: attempts.append((name, False, None, None, str(exc)[:2000]))
            if accepted: break
        mismatch = accepted and proxy["expected_country_code"] and accepted["country_code"] != proxy["expected_country_code"]
        success = bool(accepted) and not mismatch
        error = None if success else (f'expected {proxy["expected_country_code"]}, detected {accepted["country_code"]}' if mismatch else "all providers failed or disagreed")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for name, ok, result, latency, attempt_error in attempts:
                    await conn.execute("INSERT INTO proxy_check_results (id,job_id,proxy_config_id,provider,success,exit_ip,country_code,country_name,timezone,latency_ms,error) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)", uuid.uuid4(), job["id"], proxy["id"], name, ok, result and result["exit_ip"], result and result["country_code"], result and result["country_name"], result and result["timezone"], latency, attempt_error)
                if success:
                    await conn.execute("UPDATE proxy_configs SET check_status='healthy',check_error=NULL,consecutive_failures=0,exit_ip=$2,country_code=$3,country_name=$4,timezone=$5,last_checked_at=now() WHERE id=$1", proxy["id"], accepted["exit_ip"], accepted["country_code"], accepted["country_name"], accepted["timezone"])
                else:
                    await conn.execute("UPDATE proxy_configs SET consecutive_failures=consecutive_failures+1,check_status=CASE WHEN consecutive_failures+1 >= $2 THEN 'unhealthy' ELSE 'pending' END,check_error=$3,last_checked_at=now() WHERE id=$1", proxy["id"], cfg["failure_threshold"], error)
                await conn.execute("UPDATE proxy_check_jobs SET status=$2,finished_at=now(),error=$3 WHERE id=$1", job["id"], "completed" if success else "failed", error)

    async def loop(self) -> None:
        self.cipher = Fernet(KEY_FILE.read_bytes().strip())
        while self.running:
            try:
                if self.pool is None: self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
                cfg = await self.settings(); await self.enqueue_due(cfg); self.last_cycle = time.time()
                items = [item for item in [await self.claim() for _ in range(cfg["concurrency"])] if item]
                self.active = len(items)
                if items:
                    failures = [result for result in await asyncio.gather(*(self.check(item, cfg) for item in items), return_exceptions=True) if isinstance(result, Exception)]
                    self.last_error = str(failures[0]) if failures else None
                else: self.last_error = None
                self.active = 0
                await asyncio.sleep(cfg.get("poll_seconds", 5))
            except asyncio.CancelledError: raise
            except Exception as exc:
                self.active = 0; self.last_error = str(exc)
                await asyncio.sleep(5)


checker = Checker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(checker.loop()); yield; checker.running = False; task.cancel()
    if checker.pool: await checker.pool.close()

app = FastAPI(title="Proxy Checker API", version=VERSION, lifespan=lifespan)

@app.get("/api/v1/health")
async def health(): return {"status": "ok" if checker.pool and not checker.last_error else "degraded", "component": "proxy-checker", "version": VERSION}

@app.get("/api/v1/status")
async def status(): return {"active_checks": checker.active, "last_cycle": checker.last_cycle, "last_error": checker.last_error}
