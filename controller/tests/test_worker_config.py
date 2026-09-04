import pytest
from pydantic import ValidationError

from app.schemas import ProxyCreate, RunCreate
from app.worker_config import WorkerConfig


def test_run_create_accepts_complete_typed_worker_config():
    payload = RunCreate(
        identity="identity-1",
        scenario="example",
        timeout_seconds=60,
        worker_config={
            "browser": {"mode": "headless", "humanize": 2.2},
            "recording": {"video": False, "show_cursor": True},
            "fingerprint": {"window": {"width": 1280, "height": 720}},
            "vm_diagnostics": {"enabled": True, "label": "api-test"},
        },
    )
    config = payload.worker_config.overrides()
    assert config["browser"]["mode"] == "headless"
    assert config["fingerprint"]["window"] == {"width": 1280, "height": 720}
    assert payload.timeout_seconds == 60


def test_worker_config_rejects_infrastructure_and_unknown_fields():
    with pytest.raises(ValidationError):
        WorkerConfig.model_validate({"api": {"port": 9999}})
    with pytest.raises(ValidationError):
        WorkerConfig.model_validate({"browser": {"unknown": True}})


def test_custom_debug_display_requires_dimensions():
    with pytest.raises(ValidationError):
        WorkerConfig.model_validate({"browser": {"debug_display": {"size": "custom"}}})


def test_controller_proxy_contract_matches_worker_transport():
    assert ProxyCreate(name="p", host="proxy", port=8080, scheme="https").scheme == "https"
    with pytest.raises(ValidationError):
        ProxyCreate(name="p", host="proxy", port=1080, scheme="socks5")
