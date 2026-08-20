from __future__ import annotations

from pathlib import Path

import logging
import pytest

from app.actions.context import ScenarioContext
from app.plugins import PluginError, PluginManager


class DummyBrowserContext:
    pages = []


class DummyLogger:
    def info(self, *args, **kwargs):
        pass
    def warning(self, *args, **kwargs):
        pass


def ctx(manager=None):
    return ScenarioContext(
        browser_context=DummyBrowserContext(),
        artifact_dir=Path("/tmp"),
        logger=DummyLogger(),
        plugins=manager,
    )


def test_disabled_plugin_does_not_import():
    manager = PluginManager({
        "plugins": {
            "items": {
                "missing": {
                    "enabled": False,
                    "adapter": "definitely_missing_package.module:Plugin",
                }
            }
        }
    })
    assert manager.enabled_names() == []


def test_echo_plugin_invocation():
    manager = PluginManager({
        "plugins": {
            "items": {
                "echo": {
                    "enabled": True,
                    "adapter": "app.plugins.echo:EchoPlugin",
                    "config": {},
                }
            }
        }
    })
    result = manager.invoke("echo", "echo", ctx(manager), {"value": 42})
    assert result == {"echo": {"value": 42}}


def test_unknown_plugin_is_controlled():
    manager = PluginManager({})
    with pytest.raises(PluginError) as exc:
        manager.invoke("nope", "run", ctx(manager), {})
    assert exc.value.reason == "plugin_not_configured"


def test_enabled_missing_dependency_fails_only_when_used():
    manager = PluginManager({
        "plugins": {
            "items": {
                "missing": {
                    "enabled": True,
                    "adapter": "definitely_missing_package.module:Plugin",
                }
            }
        }
    })
    with pytest.raises(PluginError) as exc:
        manager.invoke("missing", "run", ctx(manager), {})
    assert exc.value.reason == "plugin_import_failed"


def test_disabled_plugin_call_is_controlled():
    manager = PluginManager({
        "plugins": {
            "items": {
                "missing": {
                    "enabled": False,
                    "adapter": "definitely_missing_package.module:Plugin",
                }
            }
        }
    })
    with pytest.raises(PluginError) as exc:
        manager.invoke("missing", "run", ctx(manager), {})
    assert exc.value.reason == "plugin_disabled"


def test_playwright_recaptcha_v2_adapter_with_fake_dependency(monkeypatch):
    from app.plugins.playwright_recaptcha import PlaywrightRecaptchaPlugin

    calls = {}

    class FakeSolver:
        def __init__(self, page, **kwargs):
            calls["page"] = page
            calls["kwargs"] = kwargs
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def solve_recaptcha(self, **kwargs):
            calls["solve_kwargs"] = kwargs
            return "fake-recaptcha-token"

    class FakeModule:
        SyncSolver = FakeSolver

    import app.plugins.playwright_recaptcha as adapter_module
    original_import = adapter_module.importlib.import_module

    def fake_import(name):
        if name == "playwright_recaptcha.recaptchav2":
            return FakeModule
        return original_import(name)

    monkeypatch.setattr(adapter_module.importlib, "import_module", fake_import)

    page = object()
    context = ctx()
    context.page = page
    context.pages = [page]
    plugin = PlaywrightRecaptchaPlugin({"default_wait": True, "image_challenge": False})
    result = plugin.invoke("solve_v2", context, {"wait": True})

    assert calls["page"] is page
    assert calls["solve_kwargs"] == {"wait": True, "image_challenge": False}
    assert result["success"] is True
    assert result["captcha_type"] == "recaptcha_v2"
    assert result["mode"] == "audio"
    assert result["token"] == "fake-recaptcha-token"


def test_playwright_recaptcha_image_mode_requires_key():
    from app.plugins.playwright_recaptcha import PlaywrightRecaptchaPlugin

    context = ctx()
    page = object()
    context.page = page
    context.pages = [page]
    plugin = PlaywrightRecaptchaPlugin({})
    with pytest.raises(PluginError) as exc:
        plugin.invoke("solve_v2", context, {"image_challenge": True})
    assert exc.value.reason == "plugin_invalid_config"


def test_playwright_recaptcha_rejects_v3_until_prepare_lifecycle_exists():
    from app.plugins.playwright_recaptcha import PlaywrightRecaptchaPlugin

    plugin = PlaywrightRecaptchaPlugin({})
    with pytest.raises(PluginError) as exc:
        plugin.invoke("solve_v3", ctx(), {})
    assert exc.value.reason == "plugin_method_not_supported"


def test_hcaptcha_challenger_adapter_bridge(monkeypatch):
    import sys
    import types
    from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin

    class FakeResponse:
        def model_dump(self, by_alias=True):
            return {"status": "ok"}

    class FakeArm:
        async def click_checkbox(self):
            return None

    class FakeAgent:
        def __init__(self, page, agent_config):
            self.page = page
            self.agent_config = agent_config
            self.robotic_arm = FakeArm()
            self.cr_list = []

        async def wait_for_challenge(self):
            self.cr_list.append(FakeResponse())

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAsyncPage:
        def __init__(self, impl):
            self.impl = impl

    agent_mod = types.ModuleType("hcaptcha_challenger.agent")
    agent_mod.AgentV = FakeAgent
    agent_mod.AgentConfig = FakeConfig
    models_mod = types.ModuleType("hcaptcha_challenger.models")
    async_mod = types.ModuleType("playwright.async_api")
    async_mod.Page = FakeAsyncPage
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger.agent", agent_mod)
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger.models", models_mod)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_mod)

    class FakePage:
        _impl_obj = object()
        def _sync(self, coro):
            import asyncio
            return asyncio.run(coro)

    class FakeCtx:
        def ensure_page(self):
            return FakePage()

    result = HCaptchaChallengerPlugin({}).invoke("solve", FakeCtx(), {})
    assert result["success"] is True
    assert result["captcha_type"] == "hcaptcha"
    assert result["response"] == {"status": "ok"}
    assert result["experimental_async_bridge"] is True

class DummyLocalHCaptchaBackend:
    def __init__(self, config):
        self.config = config
    def solve(self, page, params):
        return {"success": True, "seen_page": page is not None, "mode": self.config.get("mode")}

class TestHCaptchaBackend:
    def test_hcaptcha_custom_backend_uses_same_page(self):
        from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin

        class Ctx:
            def __init__(self):
                self.page = object()
            def ensure_page(self):
                return self.page

        plugin = HCaptchaChallengerPlugin({
            "backend": "custom",
            "backend_adapter": "test_plugins:DummyLocalHCaptchaBackend",
            "backend_config": {"mode": "local"},
        })
        result = plugin.invoke("solve", Ctx(), {})
        assert result["success"] is True
        assert result["seen_page"] is True
        assert result["mode"] == "local"
        assert result["backend"] == "custom"

    def test_hcaptcha_capabilities_do_not_require_gemini(self):
        from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin
        plugin = HCaptchaChallengerPlugin({})
        result = plugin.invoke("capabilities", None, {})
        assert result["agentv_requires_gemini"] is True
        assert "custom" in result["backends"]

def test_playwright_recaptcha_suppresses_only_pydub_syntaxwarning(monkeypatch):
    import warnings
    from app.plugins.playwright_recaptcha import PlaywrightRecaptchaPlugin
    import app.plugins.playwright_recaptcha as plugin_mod

    sentinel = object()
    def fake_import(name):
        warnings.warn_explicit(
            "invalid escape sequence '\\('",
            SyntaxWarning,
            filename="/tmp/pydub/utils.py",
            lineno=300,
            module="pydub.utils",
        )
        return sentinel

    monkeypatch.setattr(plugin_mod.importlib, "import_module", fake_import)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        loaded = PlaywrightRecaptchaPlugin._load_v2_module()
    assert loaded is sentinel
    assert caught == []

def test_hcaptcha_capabilities_expose_local_probe():
    from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin
    result = HCaptchaChallengerPlugin({}).invoke("capabilities", None, {})
    assert "local_probe" in result["diagnostics"]
    assert result["built_in_local_solver"] is False


def test_hcaptcha_local_probe_without_gemini(monkeypatch, tmp_path):
    import sys
    import types
    import app.plugins.hcaptcha_challenger as adapter_module
    from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin

    package = types.ModuleType("hcaptcha_challenger")
    package.__path__ = []
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger", package)
    monkeypatch.setattr(adapter_module.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(adapter_module.pkgutil, "walk_packages", lambda *args, **kwargs: [])
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class Locator:
        def __init__(self, count): self._count = count
        def count(self): return self._count

    class Page:
        frames = []
        def locator(self, selector):
            if "iframe" in selector:
                return Locator(1)
            return Locator(2)

    class Ctx:
        page = Page()
        artifact_dir = tmp_path
        logger = DummyLogger()
        def ensure_page(self): return self.page

    result = HCaptchaChallengerPlugin({}).invoke("local_probe", Ctx(), {})
    assert result["success"] is True
    assert result["package_version"] == "0.19.0"
    assert result["gemini_api_key_present"] is False
    assert result["hcaptcha_iframe_locator_count"] == 1
    assert Path(result["artifact"]).exists()


def test_hcaptcha_checkbox_test_clicks_current_page_checkbox():
    from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin

    class Checkbox:
        def __init__(self): self.clicked = False
        def wait_for(self, **kwargs): return None
        def click(self, **kwargs): self.clicked = True

    checkbox = Checkbox()

    class FrameLocator:
        def locator(self, selector):
            if selector == "#checkbox":
                return checkbox
            raise RuntimeError("not found")

    class ResponseNth:
        def input_value(self, **kwargs): return ""
        def get_attribute(self, name): return ""

    class ResponseLocator:
        def count(self): return 1
        def nth(self, index): return ResponseNth()

    class ChallengeLocator:
        def count(self): return 1

    class Frame:
        url = "https://newassets.hcaptcha.com/captcha/v1/checkbox"

    class Page:
        frames = [Frame()]
        def frame_locator(self, selector): return FrameLocator()
        def wait_for_timeout(self, ms): return None
        def locator(self, selector):
            if selector == "textarea[name='h-captcha-response']": return ResponseLocator()
            return ChallengeLocator()

    class Ctx:
        page = Page()
        logger = DummyLogger()
        def ensure_page(self): return self.page

    result = HCaptchaChallengerPlugin({}).invoke("checkbox_test", Ctx(), {"post_click_wait_ms": 0})
    assert checkbox.clicked is True
    assert result["checkbox_clicked"] is True
    assert result["challenge_opened"] is True
    assert result["gemini_required"] is False


def test_hcaptcha_checkbox_test_fails_cleanly_when_not_found():
    from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin

    class MissingLocator:
        def wait_for(self, **kwargs): raise RuntimeError("missing")
        def click(self, **kwargs): raise RuntimeError("missing")

    class FrameLocator:
        def locator(self, selector): return MissingLocator()

    class Page:
        frames = []
        def frame_locator(self, selector): return FrameLocator()

    class Ctx:
        page = Page()
        logger = DummyLogger()
        def ensure_page(self): return self.page

    with pytest.raises(PluginError) as exc:
        HCaptchaChallengerPlugin({}).invoke("checkbox_test", Ctx(), {"timeout_ms": 10})
    assert exc.value.reason == "hcaptcha_checkbox_not_found"


def test_hcaptcha_local_solve_test_is_non_gemini_and_controlled(monkeypatch, tmp_path):
    import sys
    import types
    import app.plugins.hcaptcha_challenger as adapter_module
    from app.plugins.hcaptcha_challenger import HCaptchaChallengerPlugin

    package = types.ModuleType("hcaptcha_challenger")
    package.__path__ = []
    agent = types.ModuleType("hcaptcha_challenger.agent")
    cli_solver = types.ModuleType("hcaptcha_challenger.cli.solver")
    tools = types.ModuleType("hcaptcha_challenger.tools")
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger", package)
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger.agent", agent)
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger.cli.solver", cli_solver)
    monkeypatch.setitem(sys.modules, "hcaptcha_challenger.tools", tools)
    monkeypatch.setattr(adapter_module.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(
        HCaptchaChallengerPlugin,
        "_checkbox_test",
        staticmethod(lambda ctx, page, params: {
            "checkbox_clicked": True,
            "challenge_opened": True,
            "response_present": False,
        }),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class Page:
        frames = []

    class Ctx:
        page = Page()
        logger = DummyLogger()
        artifact_dir = tmp_path
        def ensure_page(self): return self.page

    with pytest.raises(PluginError) as exc:
        HCaptchaChallengerPlugin({}).invoke("local_solve_test", Ctx(), {})
    assert exc.value.reason == "hcaptcha_local_solver_unavailable"
    artifact = tmp_path / "hcaptcha-local-solve-test.json"
    assert artifact.exists()
    text = artifact.read_text()
    assert '"gemini_used": false' in text
    assert '"local_solver_ready": false' in text


class TestConsentHandlerPlugin:
    def test_provider_specific_accept_all(self, tmp_path):
        from app.plugins.consent_handler import ConsentHandlerPlugin

        class Locator:
            def __init__(self, visible=False):
                self.visible = visible
                self.clicked = False
                self.first = self
            def is_visible(self, timeout=None):
                return self.visible
            def click(self, timeout=None):
                self.clicked = True
            def filter(self, has_text=None):
                return self

        accept = Locator(True)
        missing = Locator(False)

        class Scope:
            def locator(self, selector):
                if selector in {".cky-btn-accept", "button.cky-btn-accept"}:
                    return accept
                return missing
            def get_by_role(self, role, name=None):
                return missing

        class Page(Scope):
            frames = []
            main_frame = object()
            def wait_for_timeout(self, ms):
                pass

        class Ctx:
            page = Page()
            artifact_dir = tmp_path
            logger = DummyLogger()
            def ensure_page(self):
                return self.page

        plugin = ConsentHandlerPlugin({})
        result = plugin.invoke("handle", Ctx(), {
            "policy": "accept_all",
            "timeout_ms": 100,
            "required": True,
        })
        assert result["handled"] is True
        assert result["provider"] == "cookieyes"
        assert accept.clicked is True
        assert (tmp_path / "consent-handler.json").exists()

    def test_consent_not_found_is_nonfatal_by_default(self, tmp_path):
        from app.plugins.consent_handler import ConsentHandlerPlugin

        class Locator:
            first = None
            def __init__(self):
                self.first = self
            def is_visible(self, timeout=None):
                return False
            def filter(self, has_text=None):
                return self

        class Page:
            frames = []
            main_frame = object()
            def locator(self, selector):
                return Locator()
            def get_by_role(self, role, name=None):
                return Locator()
            def wait_for_timeout(self, ms):
                pass

        class Ctx:
            page = Page()
            artifact_dir = tmp_path
            logger = DummyLogger()
            def ensure_page(self):
                return self.page

        result = ConsentHandlerPlugin({}).invoke("handle", Ctx(), {
            "timeout_ms": 1,
            "required": False,
        })
        assert result["handled"] is False
        assert result["success"] is True
        assert result["reason"] == "consent_not_found"

    def test_invalid_consent_policy_is_controlled(self):
        from app.plugins.consent_handler import ConsentHandlerPlugin
        with pytest.raises(PluginError) as exc:
            ConsentHandlerPlugin({}).invoke("handle", ctx(), {"policy": "maybe"})
        assert exc.value.reason == "consent_invalid_policy"
