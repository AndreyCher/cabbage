from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Controlled configuration/layout error."""


_REQUIRED_PATHS = {
    "global_default_config",
    "local_default_config",
    "profiles_dir",
    "global_scenarios_dir",
    "local_scenarios_dir",
    "identities_dir",
    "artifacts_dir",
    "browser_source_commit",
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


def _resolve_layout_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def load_system_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    raw = _read_json(config_path, "system config")
    project = raw.get("project", {})
    worker = raw.get("worker", {})
    if not isinstance(project, dict) or not isinstance(project.get("name"), str) or not project.get("name", "").strip():
        raise ConfigError("system config project.name must be a non-empty string")
    if not isinstance(worker, dict) or not isinstance(worker.get("type"), str) or not worker.get("type", "").strip():
        raise ConfigError("system config worker.type must be a non-empty string")

    paths = raw.get("paths")
    if not isinstance(paths, dict):
        raise ConfigError("system config must contain a 'paths' object")

    missing = sorted(_REQUIRED_PATHS - set(paths))
    if missing:
        raise ConfigError(f"system config missing path keys: {', '.join(missing)}")

    base_dir = config_path.parent.resolve()
    resolved_paths: dict[str, str] = {}
    for key, value in paths.items():
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"system config paths.{key} must be a non-empty string")
        resolved_paths[key] = str(_resolve_layout_path(value.strip(), base_dir))

    return {
        **raw,
        "project": {"name": project["name"].strip()},
        "worker": {"type": worker["type"].strip().lower()},
        "config_path": str(config_path.resolve()),
        "paths": resolved_paths,
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dictionaries; scalars/lists in override replace base."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _profile_path(profile_ref: str, profiles_dir: Path) -> Path:
    candidate = Path(profile_ref)
    if candidate.is_absolute() or "/" in profile_ref or "\\" in profile_ref:
        return candidate
    filename = profile_ref if profile_ref.endswith(".json") else f"{profile_ref}.json"
    return profiles_dir / filename


def _scenario_path(name: str, global_dir: Path, local_dir: Path) -> Path:
    if not name or Path(name).name != name:
        raise ConfigError("run.scenario must be a simple scenario name, not a path")
    local_path = local_dir / f"{name}.json"
    if local_path.is_file():
        return local_path
    return global_dir / f"{name}.json"


def load_runtime_config(
    profile_ref: str,
    system_config_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve global default + optional local default + profile + one scenario."""
    system = load_system_config(system_config_path)
    paths = system["paths"]

    global_default_path = Path(paths["global_default_config"])
    local_default_path = Path(paths["local_default_config"])
    profiles_dir = Path(paths["profiles_dir"])
    global_scenarios_dir = Path(paths["global_scenarios_dir"])
    local_scenarios_dir = Path(paths["local_scenarios_dir"])

    default_cfg = _read_json(global_default_path, "global default config")
    if "scenarios" in default_cfg:
        raise ConfigError(
            "default.json must not embed 'scenarios'; store one scenario per file in a scenarios directory"
        )
    local_default_loaded = local_default_path.is_file()
    if local_default_loaded:
        local_default_cfg = _read_json(local_default_path, "local default config")
        if "scenarios" in local_default_cfg:
            raise ConfigError(
                "local default.json must not embed 'scenarios'; store one scenario per file in a scenarios directory"
            )
        default_cfg = deep_merge(default_cfg, local_default_cfg)

    profile_path = _profile_path(profile_ref, profiles_dir)
    profile_cfg = _read_json(profile_path, "profile config")
    if "scenarios" in profile_cfg:
        raise ConfigError(
            "profile config must not embed 'scenarios'; reference a scenario through run.scenario"
        )

    config = deep_merge(default_cfg, profile_cfg)

    identity = config.get("identity")
    if not isinstance(identity, str) or not identity.strip():
        raise ConfigError("resolved config must contain a non-empty 'identity'")

    selected = config.get("run", {}).get("scenario")
    if not isinstance(selected, str) or not selected.strip():
        raise ConfigError("resolved config must contain run.scenario")

    scenario_path = _scenario_path(
        selected.strip(), global_scenarios_dir, local_scenarios_dir
    )
    scenario = _read_json(scenario_path, "scenario")
    scenario_name = scenario.get("name", selected)
    if scenario_name != selected:
        raise ConfigError(
            f"scenario name mismatch: run.scenario={selected!r}, file declares {scenario_name!r}"
        )
    actions = scenario.get("actions")
    if not isinstance(actions, list):
        raise ConfigError(f"scenario {selected!r} must contain an 'actions' array")

    # Keep the existing worker runtime contract internally: downstream code
    # receives only the selected scenario under cfg['scenarios'].
    config["scenarios"] = {
        selected: {
            "actions": actions,
            **({"version": scenario["version"]} if "version" in scenario else {}),
        }
    }

    layout = {
        "project_name": system["project"]["name"],
        "worker_type": system["worker"]["type"],
        "system_config": system["config_path"],
        "global_default_config": str(global_default_path),
        "local_default_config": str(local_default_path),
        "local_default_loaded": local_default_loaded,
        "profile_config": str(profile_path.resolve()),
        "scenario_config": str(scenario_path.resolve()),
        **paths,
    }
    return config, layout


def load_config(path: str) -> dict[str, Any]:
    """Legacy combined-config loader retained only for migration/tests."""
    config_path = Path(path)
    config = _read_json(config_path, "legacy config")
    if not config.get("identity"):
        raise ConfigError("Config must contain a non-empty 'identity'")
    scenarios = config.get("scenarios", {})
    selected = config.get("run", {}).get("scenario")
    if not selected or selected not in scenarios:
        raise ConfigError(
            f"run.scenario must reference one of: {', '.join(scenarios.keys()) or '<none>'}"
        )
    return config
