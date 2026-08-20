from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config_loader import ConfigError, deep_merge, load_runtime_config


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def make_layout(tmp_path: Path):
    cfg = tmp_path / "worker-config"
    shared = tmp_path / "workers-config"
    profiles = cfg / "profiles"
    scenarios = shared / "scenarios"
    identities = tmp_path / "identities"
    artifacts = tmp_path / "artifacts" / "results"
    browser_commit = tmp_path / "browser" / "SOURCE_COMMIT"

    system = cfg / "config.json"
    write_json(system, {
        "schema_version": 1,
        "project": {"name": "cabbage"},
        "worker": {"type": "firefox"},
        "paths": {
            "global_default_config": str(shared / "default.json"),
            "local_default_config": str(cfg / "default.json"),
            "profiles_dir": str(profiles),
            "global_scenarios_dir": str(scenarios),
            "local_scenarios_dir": str(cfg / "scenarios"),
            "identities_dir": str(identities),
            "artifacts_dir": str(artifacts),
            "browser_source_commit": str(browser_commit),
        },
    })
    return system, shared, cfg, profiles, scenarios


def test_deep_merge_recurses_and_replaces_lists():
    merged = deep_merge(
        {"browser": {"mode": "virtual", "x": 1}, "languages": ["en"]},
        {"browser": {"mode": "debug"}, "languages": ["fr-FR", "fr"]},
    )
    assert merged == {
        "browser": {"mode": "debug", "x": 1},
        "languages": ["fr-FR", "fr"],
    }


def test_runtime_config_merges_default_profile_and_external_scenario(tmp_path):
    system, shared, cfg, profiles, scenarios = make_layout(tmp_path)

    write_json(shared / "default.json", {
        "identity": "",
        "run": {"scenario": "identity"},
        "browser": {"mode": "virtual", "humanize": 1.8},
        "recording": {"video": True, "show_cursor": False},
    })
    write_json(profiles / "test-user-004.json", {
        "identity": "test-user-004",
        "run": {"scenario": "trustpilot"},
        "browser": {"mode": "debug"},
        "recording": {"show_cursor": True},
    })
    write_json(scenarios / "trustpilot.json", {
        "name": "trustpilot",
        "version": 1,
        "actions": [{"type": "open", "url": "https://example.com"}],
    })

    resolved, layout = load_runtime_config("test-user-004", system)

    assert resolved["identity"] == "test-user-004"
    assert resolved["browser"] == {"mode": "debug", "humanize": 1.8}
    assert resolved["recording"] == {"video": True, "show_cursor": True}
    assert resolved["scenarios"]["trustpilot"]["actions"][0]["type"] == "open"
    assert layout["project_name"] == "cabbage"
    assert layout["worker_type"] == "firefox"
    assert layout["local_default_loaded"] is False
    assert layout["profile_config"].endswith("profiles/test-user-004.json")
    assert layout["scenario_config"].endswith("scenarios/trustpilot.json")


def test_optional_local_default_overrides_global_default(tmp_path):
    system, shared, cfg, profiles, scenarios = make_layout(tmp_path)
    write_json(shared / "default.json", {
        "identity": "",
        "run": {"scenario": "x"},
        "browser": {"mode": "virtual", "humanize": 1.8},
    })
    write_json(cfg / "default.json", {"browser": {"mode": "debug"}})
    write_json(profiles / "p.json", {"identity": "p"})
    write_json(scenarios / "x.json", {"name": "x", "actions": []})

    resolved, layout = load_runtime_config("p", system)

    assert resolved["browser"] == {"mode": "debug", "humanize": 1.8}
    assert layout["local_default_loaded"] is True


def test_local_scenario_fully_replaces_global_scenario(tmp_path):
    system, shared, cfg, profiles, scenarios = make_layout(tmp_path)
    write_json(shared / "default.json", {
        "identity": "",
        "run": {"scenario": "x"},
    })
    write_json(profiles / "p.json", {"identity": "p"})
    write_json(scenarios / "x.json", {
        "name": "x",
        "actions": [{"type": "open", "url": "https://global.example"}],
    })
    write_json(cfg / "scenarios" / "x.json", {
        "name": "x",
        "actions": [{"type": "open", "url": "https://local.example"}],
    })

    resolved, layout = load_runtime_config("p", system)

    assert resolved["scenarios"]["x"]["actions"] == [
        {"type": "open", "url": "https://local.example"}
    ]
    assert layout["scenario_config"].endswith("worker-config/scenarios/x.json")


def test_profile_cannot_embed_scenarios(tmp_path):
    system, shared, cfg, profiles, scenarios = make_layout(tmp_path)
    write_json(shared / "default.json", {"identity": "", "run": {"scenario": "x"}})
    write_json(profiles / "p.json", {
        "identity": "p",
        "scenarios": {"x": {"actions": []}},
    })
    write_json(scenarios / "x.json", {"name": "x", "actions": []})

    with pytest.raises(ConfigError, match="must not embed 'scenarios'"):
        load_runtime_config("p", system)


def test_scenario_name_must_match_reference(tmp_path):
    system, shared, cfg, profiles, scenarios = make_layout(tmp_path)
    write_json(shared / "default.json", {"identity": "", "run": {"scenario": "x"}})
    write_json(profiles / "p.json", {"identity": "p"})
    write_json(scenarios / "x.json", {"name": "other", "actions": []})

    with pytest.raises(ConfigError, match="scenario name mismatch"):
        load_runtime_config("p", system)


def test_system_config_requires_project_and_worker_metadata(tmp_path):
    cfg = tmp_path / "config.json"
    write_json(cfg, {
        "schema_version": 1,
        "paths": {
            "global_default_config": "default.json",
            "local_default_config": "local-default.json",
            "profiles_dir": "profiles",
            "global_scenarios_dir": "scenarios",
            "local_scenarios_dir": "local-scenarios",
            "identities_dir": "identities",
            "artifacts_dir": "artifacts",
            "browser_source_commit": "SOURCE_COMMIT"
        }
    })
    from app.config_loader import load_system_config
    with pytest.raises(ConfigError, match="project.name"):
        load_system_config(cfg)
