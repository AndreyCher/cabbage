import sys

import pytest

from app.main import parse_args


@pytest.mark.parametrize(
    ("operation", "reset", "update"),
    [("reset", True, False), ("update", False, True)],
)
def test_identity_operation_environment_bridge(monkeypatch, operation, reset, update):
    monkeypatch.setenv("WORKER_IDENTITY_OPERATION", operation)
    monkeypatch.setenv("WORKER_SYSTEM_CONFIG", "/config/config.json")
    monkeypatch.setenv("WORKER_PROFILE", "profile")
    monkeypatch.setattr(sys, "argv", ["worker"])
    args = parse_args()
    assert args.reset_identity is reset
    assert args.update_identity is update


def test_identity_operation_environment_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("WORKER_IDENTITY_OPERATION", "destroy")
    monkeypatch.setattr(sys, "argv", ["worker"])
    with pytest.raises(SystemExit):
        parse_args()
