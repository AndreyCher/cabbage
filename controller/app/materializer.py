from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .worker_config import DEFAULT_DOMAIN_CONFIG

if TYPE_CHECKING:
    from .models import Run


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class RunMaterializer:
    def __init__(self, root: Path) -> None:
        self.root = root

    def materialize(
        self,
        run: "Run",
        proxy: dict[str, Any] | None = None,
        identity_config: dict[str, Any] | None = None,
        worker_defaults: dict[str, Any] | None = None,
    ) -> str:
        run_root = self.root / str(run.id)
        (run_root / "profiles").mkdir(parents=True, exist_ok=True)
        (run_root / "scenarios").mkdir(parents=True, exist_ok=True)
        infrastructure = {
            "identity": "",
            "run": {"scenario": run.scenario.name},
            "api": {"enabled": True, "host": "0.0.0.0", "port": 8090},
            "proxy": {"enabled": False},
        }
        default = deep_merge(infrastructure, DEFAULT_DOMAIN_CONFIG)
        default = deep_merge(default, worker_defaults or {})
        resolved = deep_merge(default, identity_config or {})
        resolved = deep_merge(resolved, run.overrides or {})
        if run.debug:
            resolved.setdefault("browser", {})["mode"] = "debug"
        resolved["identity"] = run.identity
        resolved["run"] = {
            **resolved.get("run", {}),
            "scenario": run.scenario.name,
            "controller_run_id": str(run.id),
        }
        if proxy is not None:
            resolved["proxy"] = proxy
        elif run.proxy_mode == "disabled":
            resolved["proxy"] = {"enabled": False}
        profile = {key: value for key, value in resolved.items() if key != "identity"}
        profile["identity"] = run.identity
        scenario = dict(run.scenario.definition)
        scenario.setdefault("name", run.scenario.name)
        system = {
            "project": {"name": "cabbage"}, "worker": {"type": "firefox"},
            "paths": {
                "global_default_config": str(run_root / "default.json"),
                "local_default_config": str(run_root / "missing-local-default.json"),
                "profiles_dir": str(run_root / "profiles"),
                "global_scenarios_dir": str(run_root / "scenarios"),
                "local_scenarios_dir": str(run_root / "missing-local-scenarios"),
                "identities_dir": "/identities", "artifacts_dir": "/artifacts",
                "browser_source_commit": "/opt/camoufox-custom/SOURCE_COMMIT",
            },
        }
        for path, value in ((run_root / "default.json", default), (run_root / "profiles/run.json", profile), (run_root / f"scenarios/{run.scenario.name}.json", scenario), (run_root / "config.json", system)):
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        return f"/controller-runs/{run.id}/config.json"

    @staticmethod
    def materialize_identity_profile(identity: str, config: dict[str, Any], identities_root: Path) -> Path:
        """Synchronize the Controller-owned fingerprint profile for the next worker run."""
        identity_root = identities_root / identity
        identity_root.mkdir(parents=True, exist_ok=True)
        target = identity_root / "config.json"
        current: dict[str, Any] = {}
        if target.is_file():
            try:
                current = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                current = {}
        profile = {
            **current,
            "schema_version": 1,
            "identity": identity,
            "fingerprint": dict(config.get("fingerprint") or {}),
        }
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        temporary.replace(target)
        return target
