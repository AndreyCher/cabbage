from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _install_camoufox_stubs():
    camoufox = types.ModuleType("camoufox")
    sync_api = types.ModuleType("camoufox.sync_api")
    utils = types.ModuleType("camoufox.utils")

    class DummyCamoufox:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    sync_api.Camoufox = DummyCamoufox
    utils.launch_options = lambda **kwargs: {"env": {}}
    camoufox.sync_api = sync_api
    camoufox.utils = utils
    sys.modules["camoufox"] = camoufox
    sys.modules["camoufox.sync_api"] = sync_api
    sys.modules["camoufox.utils"] = utils

    browserforge = types.ModuleType("browserforge")
    fingerprints = types.ModuleType("browserforge.fingerprints")

    class DummyScreen:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fingerprints.Screen = DummyScreen
    browserforge.fingerprints = fingerprints
    sys.modules["browserforge"] = browserforge
    sys.modules["browserforge.fingerprints"] = fingerprints


def test_generation_uses_public_locale_api_and_not_manual_locale_all():
    _install_camoufox_stubs()
    identity = importlib.import_module("app.identity")
    cfg = {
        "browser": {"humanize": 1.8, "enable_cache": True},
        "proxy": {"enabled": False},
        "fingerprint": {
            "locale": "de-DE",
            "languages": ["en-US", "en", "de-DE", "de"],
            "timezone": "Europe/Berlin",
        },
    }
    kwargs = identity._generation_kwargs(cfg)
    assert kwargs["locale"] == ["de-DE", "en-US", "en", "de"]
    assert "locale:all" not in kwargs["config"]
    assert kwargs["config"]["timezone"] == "Europe/Berlin"
    assert kwargs["i_know_what_im_doing"] is True


def test_runtime_reconstructs_locale_and_strips_low_level_locale_keys():
    _install_camoufox_stubs()
    browser = importlib.import_module("app.browser")
    cfg = {
        "browser": {"mode": "headless", "humanize": 1.8, "enable_cache": True},
        "proxy": {"enabled": False},
        "recording": {"video": False},
    }
    persisted = {
        "locale:language": "de",
        "locale:region": "DE",
        "locale:script": "Latn",
        "locale:all": "de-DE, de, en-US, en",
        "timezone": "Europe/Berlin",
        "canvas:seed": 123,
    }
    state = {
        "camou_config": persisted,
        "paths": {"profile": Path("/tmp/profile")},
    }
    kwargs = browser.build_camoufox_kwargs(cfg, state)
    assert kwargs["locale"] == ["de-DE", "de", "en-US", "en"]
    assert kwargs["config"]["timezone"] == "Europe/Berlin"
    assert kwargs["config"]["canvas:seed"] == 123
    assert not any(key.startswith("locale:") for key in kwargs["config"])
    assert "geoip" not in kwargs
    assert kwargs["i_know_what_im_doing"] is True
