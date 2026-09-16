from __future__ import annotations
import copy, json
from pathlib import Path
from typing import Any

class ConfigError(ValueError):
    pass

_REQUIRED_PATHS = {
    "global_default_config", "local_default_config", "profiles_dir",
    "global_scenarios_dir", "local_scenarios_dir", "identities_dir", "artifacts_dir",
}

def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{label} must contain a JSON object: {path}")
    return data

def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result

def load_system_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    raw = _read_json(config_path, "system config")
    project, worker, paths = raw.get("project", {}), raw.get("worker", {}), raw.get("paths")
    if not isinstance(project.get("name"), str) or not project["name"].strip():
        raise ConfigError("system config project.name must be a non-empty string")
    if not isinstance(worker.get("type"), str) or not worker["type"].strip():
        raise ConfigError("system config worker.type must be a non-empty string")
    if not isinstance(paths, dict):
        raise ConfigError("system config must contain a 'paths' object")
    missing = sorted(_REQUIRED_PATHS - set(paths))
    if missing:
        raise ConfigError(f"system config missing path keys: {', '.join(missing)}")
    base = config_path.parent.resolve()
    resolved = {}
    for key, value in paths.items():
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"system config paths.{key} must be a non-empty string")
        p = Path(value)
        resolved[key] = str(p if p.is_absolute() else (base / p).resolve())
    return {**raw, "project":{"name":project["name"].strip()}, "worker":{"type":worker["type"].strip().lower()}, "config_path":str(config_path.resolve()), "paths":resolved}

def _profile_path(ref: str, profiles: Path) -> Path:
    p = Path(ref)
    if p.is_absolute() or "/" in ref or "\\" in ref:
        return p
    return profiles / (ref if ref.endswith(".json") else f"{ref}.json")

def load_runtime_config(profile_ref: str, system_config_path: str | Path):
    system = load_system_config(system_config_path); paths = system["paths"]
    gd, ld = Path(paths["global_default_config"]), Path(paths["local_default_config"])
    profiles = Path(paths["profiles_dir"]); gs, ls = Path(paths["global_scenarios_dir"]), Path(paths["local_scenarios_dir"])
    cfg = _read_json(gd, "global default config")
    local_loaded = ld.is_file()
    if local_loaded: cfg = deep_merge(cfg, _read_json(ld, "local default config"))
    pp = _profile_path(profile_ref, profiles)
    launch = _read_json(pp, "profile config")
    identity_ref = launch.get("identity", cfg.get("identity"))
    if not isinstance(identity_ref, str) or not identity_ref or identity_ref in {".", ".."} or "/" in identity_ref or "\\" in identity_ref:
        raise ConfigError("identity must be a non-empty directory name")
    identity_path = Path(paths["identities_dir"]) / identity_ref / "config.json"
    if identity_path.is_file():
        identity_cfg = _read_json(identity_path, "identity config")
        # Apply only the new Android-owned domains; preserve existing precedence
        # for all unrelated worker settings.
        cfg = deep_merge(cfg, {k: identity_cfg[k] for k in ("telephony", "phone_number_provider") if k in identity_cfg})
    cfg = deep_merge(cfg, launch)
    for domain in ("telephony", "phone_number_provider"):
        value = cfg.get(domain, {})
        if not isinstance(value, dict) or not isinstance(value.get("enabled", False), bool):
            raise ConfigError(f"{domain} must be an object with boolean enabled")
    provider = cfg.get("phone_number_provider", {})
    if not isinstance(provider.get("release_on_finish", True), bool):
        raise ConfigError("phone_number_provider.release_on_finish must be boolean")
    identity = cfg.get("identity"); selected = cfg.get("run", {}).get("scenario")
    if not isinstance(identity, str) or not identity.strip(): raise ConfigError("resolved config must contain a non-empty 'identity'")
    if not isinstance(selected, str) or not selected.strip(): raise ConfigError("resolved config must contain run.scenario")
    selected = selected.strip(); lp = ls / f"{selected}.json"; sp = lp if lp.is_file() else gs / f"{selected}.json"
    scenario = _read_json(sp, "scenario")
    if scenario.get("name", selected) != selected: raise ConfigError(f"scenario name mismatch: run.scenario={selected!r}")
    actions = scenario.get("actions")
    if not isinstance(actions, list): raise ConfigError(f"scenario {selected!r} must contain an 'actions' array")
    cfg["scenarios"] = {selected: {"actions": actions, **({"version":scenario["version"]} if "version" in scenario else {})}}
    layout = {"project_name":system["project"]["name"], "worker_type":system["worker"]["type"], "system_config":system["config_path"], "global_default_config":str(gd), "local_default_config":str(ld), "local_default_loaded":local_loaded, "profile_config":str(pp.resolve()), "scenario_config":str(sp.resolve()), **paths}
    return cfg, layout
