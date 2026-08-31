import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.materializer import RunMaterializer, deep_merge


def test_deep_merge_keeps_unmodified_nested_values():
    assert deep_merge({"browser": {"mode": "virtual", "humanize": 1}}, {"browser": {"humanize": 2}}) == {"browser": {"mode": "virtual", "humanize": 2}}


def test_materializer_creates_worker_layout(tmp_path: Path):
    run = SimpleNamespace(
        id=uuid4(), identity="test-user-001", debug=False, proxy_mode="disabled",
        overrides={"recording": {"video": False}},
        scenario=SimpleNamespace(name="example", definition={"name": "example", "actions": []}),
    )
    path = RunMaterializer(tmp_path).materialize(run)
    root = tmp_path / str(run.id)
    assert path.endswith("/config.json")
    assert (root / "config.json").is_file()
    assert (root / "profiles/run.json").is_file()
    assert (root / "scenarios/example.json").is_file()
    profile = json.loads((root / "profiles/run.json").read_text())
    assert profile["run"]["controller_run_id"] == str(run.id)
    assert profile["plugins"]["items"]["consent-handler"]["enabled"] is True
    assert profile["browser"]["debug_display"]["size"] == "identity"


def test_materializer_forces_debug_browser_mode(tmp_path: Path):
    run = SimpleNamespace(
        id=uuid4(), identity="test-user-001", debug=True, proxy_mode="disabled",
        overrides={},
        scenario=SimpleNamespace(name="example", definition={"name": "example", "actions": []}),
    )
    RunMaterializer(tmp_path).materialize(run, identity_config={"browser": {"mode": "headless"}})
    profile = json.loads((tmp_path / str(run.id) / "profiles/run.json").read_text())
    assert profile["browser"]["mode"] == "debug"


def test_materializer_synchronizes_controller_owned_identity_profile(tmp_path: Path):
    target = RunMaterializer.materialize_identity_profile(
        "identity-1",
        {"fingerprint": {"locale": "uk-UA", "window": {"width": 1280, "height": 720}}},
        tmp_path,
    )
    profile = json.loads(target.read_text())
    assert profile["identity"] == "identity-1"
    assert profile["fingerprint"]["locale"] == "uk-UA"

    RunMaterializer.materialize_identity_profile(
        "identity-1", {"fingerprint": {"locale": "en-US"}}, tmp_path
    )
    updated = json.loads(target.read_text())
    assert updated["fingerprint"] == {"locale": "en-US"}


def test_database_worker_defaults_are_applied_before_identity_and_run(tmp_path: Path):
    run = SimpleNamespace(
        id=uuid4(), identity="identity-1", debug=False, proxy_mode="disabled",
        overrides={"browser": {"humanize": 3.0}},
        scenario=SimpleNamespace(name="example", definition={"name": "example", "actions": []}),
    )
    RunMaterializer(tmp_path).materialize(
        run,
        identity_config={"recording": {"video": False}},
        worker_defaults={"browser": {"humanize": 2.0}, "recording": {"video": True}},
    )
    profile = json.loads((tmp_path / str(run.id) / "profiles/run.json").read_text())
    assert profile["browser"]["humanize"] == 3.0
    assert profile["recording"]["video"] is False
