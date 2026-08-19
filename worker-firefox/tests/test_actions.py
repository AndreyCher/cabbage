from __future__ import annotations

import logging
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from app.actions import ActionEngine, ScenarioContext, registry
from app.runtime import FatalActionError


EXPECTED_ACTIONS = {
    "open",
    "wait",
    "scroll",
    "mouse_move",
    "mouse_move_random",
    "screenshot",
    "new_tab",
    "switch_tab",
    "click",
    "type",
    "press",
    "click_link_by_index",
    "go_back",
    "wait_input",
    "plugin_call",
    "select",
    "webhook",
    "mouse_press",
    "hover",
}


class FakeMouse:
    def __init__(self):
        self.wheels = []
    def wheel(self, x, y):
        self.wheels.append((x, y))


class FakePage:
    def __init__(self, url="about:blank"):
        self.url = url
        self.mouse = FakeMouse()
        self.brought_to_front = False
    def bring_to_front(self):
        self.brought_to_front = True
    def wait_for_timeout(self, timeout_ms):
        time.sleep(timeout_ms / 1000.0)


class FakeBrowserContext:
    def __init__(self):
        self.pages = [FakePage()]
        self._handlers = {}
    def on(self, event, callback):
        self._handlers.setdefault(event, []).append(callback)
    def _emit(self, event, value):
        for callback in self._handlers.get(event, []):
            callback(value)
    def new_page(self):
        page = FakePage()
        self.pages.append(page)
        self._emit("page", page)
        return page
    def open_site_tab(self, url="https://example.test/new"):
        page = FakePage(url)
        self.pages.append(page)
        self._emit("page", page)
        return page


class BlockingAction:
    name = "blocking"
    def execute(self, ctx, action, index):
        time.sleep(5)
        return {}


class ActionFrameworkTests(unittest.TestCase):
    def test_builtin_actions_are_registered(self):
        self.assertEqual(set(registry.names()), EXPECTED_ACTIONS)

    def test_scenario_context_reuses_existing_page(self):
        browser = FakeBrowserContext()
        ctx = ScenarioContext(browser, Path("/tmp"), logging.getLogger("test"))
        page = ctx.ensure_page()
        self.assertIs(page, browser.pages[0])
        self.assertEqual(ctx.pages, [page])


    def test_site_opened_tab_is_tracked_and_switchable(self):
        browser = FakeBrowserContext()
        ctx = ScenarioContext(browser, Path("/tmp"), logging.getLogger("test-tabs"))
        original = ctx.ensure_page()
        popup = browser.open_site_tab("https://example.test/signup")
        self.assertEqual(ctx.pages, [original, popup])
        page, index = ctx.switch_page(index=1, timeout_ms=100)
        self.assertIs(page, popup)
        self.assertEqual(index, 1)
        self.assertTrue(popup.brought_to_front)

    def test_switch_tab_supports_newest_target(self):
        browser = FakeBrowserContext()
        ctx = ScenarioContext(browser, Path("/tmp"), logging.getLogger("test-tabs-newest"))
        ctx.ensure_page()
        popup = browser.open_site_tab("https://example.test/newest")
        page, index = ctx.switch_page(target="newest", timeout_ms=100)
        self.assertIs(page, popup)
        self.assertEqual(index, 1)

    def test_switch_tab_pumps_playwright_while_waiting(self):
        class DeferredEventBrowserContext(FakeBrowserContext):
            def __init__(self):
                super().__init__()
                self.pending_page = None

            def queue_site_tab(self, url):
                self.pending_page = FakePage(url)

        browser = DeferredEventBrowserContext()
        ctx = ScenarioContext(browser, Path("/tmp"), logging.getLogger("test-tabs-pump"))
        page = ctx.ensure_page()

        def pump(timeout_ms):
            if browser.pending_page is not None:
                popup = browser.pending_page
                browser.pending_page = None
                browser.pages.append(popup)
                browser._emit("page", popup)
            time.sleep(timeout_ms / 1000.0)

        page.wait_for_timeout = pump
        browser.queue_site_tab("https://example.test/pumped")
        switched, index = ctx.switch_page(index=1, timeout_ms=500)
        self.assertEqual(index, 1)
        self.assertEqual(switched.url, "https://example.test/pumped")

    def test_switch_tab_waits_for_requested_index(self):
        import threading
        browser = FakeBrowserContext()
        ctx = ScenarioContext(browser, Path("/tmp"), logging.getLogger("test-tabs-wait"))
        ctx.ensure_page()
        timer = threading.Timer(0.05, lambda: browser.open_site_tab("https://example.test/later"))
        timer.start()
        try:
            page, index = ctx.switch_page(index=1, timeout_ms=500)
        finally:
            timer.cancel()
        self.assertEqual(index, 1)
        self.assertEqual(page.url, "https://example.test/later")

    def test_engine_keeps_legacy_page_properties_and_runs_scroll(self):
        browser = FakeBrowserContext()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger("test"))
            engine.page = browser.pages[0]
            engine.pages = [browser.pages[0]]
            results = engine.run([{"type": "scroll", "delta_x": 12, "delta_y": -34}])
        self.assertEqual(results[0]["status"], "PASS")
        self.assertEqual(results[0]["data"], {"delta_x": 12, "delta_y": -34})
        self.assertEqual(browser.pages[0].mouse.wheels, [(12, -34)])

    def test_unknown_action_keeps_fail_fast_behavior(self):
        browser = FakeBrowserContext()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger("test"))
            with self.assertRaisesRegex(ValueError, "Unsupported action type"):
                engine.run([{"type": "does_not_exist"}])

    def test_engine_watchdog_interrupts_stuck_timeout_action(self):
        browser = FakeBrowserContext()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger("test"))
            with patch.object(registry, "get", return_value=BlockingAction()):
                started = time.monotonic()
                with self.assertRaises(FatalActionError) as caught:
                    engine.run([{"type": "blocking", "action_timeout_ms": 100}])
                elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.reason, "action_timeout")
        self.assertLess(elapsed, 1.5)

    def test_timeout_ms_derives_watchdog_with_transport_grace(self):
        self.assertEqual(
            ActionEngine._watchdog_timeout_sec({"type": "click", "timeout_ms": 15000}),
            17.0,
        )


if __name__ == "__main__":
    unittest.main()

class CleanupAndDefaultWatchdogTests(unittest.TestCase):
    def test_default_browser_action_watchdog_is_30_seconds(self):
        self.assertEqual(ActionEngine._watchdog_timeout_sec({}, "scroll"), 30.0)
        self.assertIsNone(ActionEngine._watchdog_timeout_sec({}, "wait"))
        self.assertIsNone(ActionEngine._watchdog_timeout_sec({}, "wait_input"))

    def test_bounded_browser_cleanup_interrupts_stuck_exit(self):
        import logging
        import time
        from app.browser_cleanup import BrowserCleanupTimeout, bounded_manager_exit

        class StuckManager:
            def __exit__(self, exc_type, exc, tb):
                time.sleep(2.0)
                return False

        started = time.monotonic()
        with self.assertRaises(BrowserCleanupTimeout):
            bounded_manager_exit(
                StuckManager(),
                (None, None, None),
                logging.getLogger("cleanup-test"),
                timeout_sec=0.1,
            )
        self.assertLess(time.monotonic() - started, 1.0)

class ControlledPluginErrorTests(unittest.TestCase):
    def test_plugin_error_becomes_structured_fatal_action_without_traceback_path(self):
        from app.plugins.base import PluginError

        class FailingPlugins:
            def invoke(self, name, method, ctx, params):
                raise PluginError(
                    "Unknown plugin: missing",
                    reason="plugin_not_configured",
                    details={"plugin": "missing", "method": method},
                )

        browser = FakeBrowserContext()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(
                browser,
                Path(tmp),
                logging.getLogger("plugin-error-test"),
                plugins=FailingPlugins(),
            )
            engine.page = browser.pages[0]
            engine.pages = [browser.pages[0]]
            with self.assertRaises(FatalActionError) as caught:
                engine.run([{
                    "type": "plugin_call",
                    "plugin": "missing",
                    "method": "echo",
                }])
        self.assertEqual(caught.exception.reason, "plugin_not_configured")
        self.assertEqual(caught.exception.details["plugin"], "missing")

class FakeSelectLocator:
    def __init__(self, tag='SELECT'):
        self.tag = tag
        self.selected = None
        self.clicked = False
        self.waited = False
        self.first = self
    def wait_for(self, state='visible', timeout=None):
        self.waited = True
    def evaluate(self, script):
        return self.tag
    def select_option(self, **kwargs):
        kwargs.pop('timeout', None)
        self.selected = kwargs
        if 'value' in kwargs:
            return [kwargs['value']]
        if 'label' in kwargs:
            return [kwargs['label']]
        return [str(kwargs['index'])]
    def click(self, timeout=None):
        self.clicked = True
    def filter(self, has_text=None):
        self.filter_text = has_text
        return self
    def nth(self, index):
        self.nth_index = index
        return self

class FakeSelectPage(FakePage):
    def __init__(self, tag='SELECT'):
        super().__init__()
        self.trigger = FakeSelectLocator(tag)
        self.option = FakeSelectLocator('DIV')
        self.role_calls = []
        self.locator_calls = []
    def locator(self, selector):
        self.locator_calls.append(selector)
        if selector == '#country':
            return self.trigger
        return self.option
    def get_by_role(self, role, name=None, exact=None):
        self.role_calls.append((role, name, exact))
        return self.option

class FakeSelectBrowserContext:
    def __init__(self, page):
        self.pages = [page]

class SelectActionTests(unittest.TestCase):
    def test_native_select_by_value(self):
        page = FakeSelectPage('SELECT')
        browser = FakeSelectBrowserContext(page)
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger('select-native'))
            result = engine.run([{
                'type': 'select', 'selector': '#country', 'value': 'DE'
            }])[0]
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['data']['method'], 'native')
        self.assertEqual(page.trigger.selected, {'value': 'DE'})

    def test_custom_select_by_label(self):
        page = FakeSelectPage('DIV')
        browser = FakeSelectBrowserContext(page)
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger('select-custom'))
            result = engine.run([{
                'type': 'select', 'selector': '#country', 'label': 'Germany'
            }])[0]
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['data']['method'], 'custom')
        self.assertTrue(page.trigger.clicked)
        self.assertTrue(page.option.clicked)
        self.assertEqual(page.role_calls, [('option', 'Germany', True)])

    def test_select_requires_exactly_one_target(self):
        page = FakeSelectPage('SELECT')
        browser = FakeSelectBrowserContext(page)
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger('select-invalid'))
            with self.assertRaisesRegex(ValueError, "exactly one"):
                engine.run([{
                    'type': 'select', 'selector': '#country', 'value': 'DE', 'label': 'Germany'
                }])


class WebhookActionTests(unittest.TestCase):
    def test_webhook_saves_json_for_following_actions(self):
        from app.runtime import RuntimeContext
        from unittest.mock import Mock, patch
        browser = FakeBrowserContext()
        runtime = RuntimeContext("identity-1", "run-1", "scenario")
        response = Mock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"login": "alice", "country_code": "DE"}
        response.raise_for_status.return_value = None
        with tempfile.TemporaryDirectory() as tmp, patch("app.actions.webhook.requests.request", return_value=response) as request:
            engine = ActionEngine(browser, Path(tmp), logging.getLogger("webhook-test"), runtime=runtime)
            result = engine.run([{
                "type": "webhook", "url": "http://mock/api/profile", "method": "POST",
                "json": {"id": "user-001"}, "save_as": "profile", "timeout_ms": 1000
            }])[0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(runtime.resolve_value("{{webhook.profile.login}}"), "alice")
        self.assertEqual(runtime.resolve_value("code={{webhook.profile.country_code}}"), "code=DE")
        request.assert_called_once()


class HoldMouse:
    def __init__(self):
        self.moves = []
        self.downs = []
        self.ups = []
    def move(self, x, y):
        self.moves.append((x, y))
    def down(self, button="left"):
        self.downs.append(button)
    def up(self, button="left"):
        self.ups.append(button)


class HoldLocator:
    def __init__(self, box=None):
        self.first = self
        self.box = box or {"x": 100, "y": 200, "width": 40, "height": 20}
        self.waited = False
    def wait_for(self, state="visible", timeout=None):
        self.waited = True
    def bounding_box(self, timeout=None):
        return dict(self.box)


class HoldFrameScope:
    def __init__(self, locator):
        self._locator = locator
        self.frames = []
    def frame_locator(self, selector):
        self.frames.append(selector)
        return self
    def locator(self, selector):
        self.selector = selector
        return self._locator


class HoldPage:
    def __init__(self):
        self.url = "https://example.test"
        self.mouse = HoldMouse()
        self.target = HoldLocator()
        self.scope = HoldFrameScope(self.target)
        self.waits = []
    def locator(self, selector):
        self.scope.selector = selector
        return self.target
    def frame_locator(self, selector):
        self.scope.frames.append(selector)
        return self.scope
    def wait_for_timeout(self, timeout_ms):
        self.waits.append(timeout_ms)


class HoldBrowser:
    def __init__(self, page):
        self.pages = [page]


class MousePressActionTests(unittest.TestCase):
    def test_mouse_press_holds_dom_target_and_releases(self):
        page = HoldPage()
        runtime = None
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(HoldBrowser(page), Path(tmp), logging.getLogger("mouse-press"))
            result = engine.run([{
                "type": "mouse_press",
                "selector": "#hold",
                "button": "left",
                "hold_ms": 10000,
                "timeout_ms": 15000,
            }])[0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(page.mouse.moves, [(120.0, 210.0)])
        self.assertEqual(page.mouse.downs, ["left"])
        self.assertEqual(page.mouse.ups, ["left"])
        self.assertEqual(page.waits, [10000])

    def test_mouse_press_supports_iframe_chain(self):
        page = HoldPage()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(HoldBrowser(page), Path(tmp), logging.getLogger("mouse-press-frame"))
            engine.run([{
                "type": "mouse_press",
                "frames": ["iframe#outer", "iframe#inner"],
                "selector": "div[role='button']",
                "hold_ms": 250,
                "timeout_ms": 15000,
            }])
        self.assertEqual(page.scope.frames, ["iframe#outer", "iframe#inner"])
        self.assertEqual(page.scope.selector, "div[role='button']")
        self.assertEqual(page.waits, [250])

    def test_mouse_press_supports_absolute_position(self):
        page = HoldPage()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(HoldBrowser(page), Path(tmp), logging.getLogger("mouse-press-pos"))
            engine.run([{
                "type": "mouse_press",
                "position": {"x": 300, "y": 400},
                "offset": {"x": 5, "y": -10},
                "hold_ms": 0,
                "timeout_ms": 5000,
            }])
        self.assertEqual(page.mouse.moves, [(305.0, 390.0)])
        self.assertEqual(page.mouse.downs, ["left"])
        self.assertEqual(page.mouse.ups, ["left"])
        self.assertEqual(page.waits, [])

    def test_mouse_press_watchdog_includes_hold_duration(self):
        self.assertEqual(
            ActionEngine._watchdog_timeout_sec(
                {"type": "mouse_press", "timeout_ms": 15000, "hold_ms": 10000},
                "mouse_press",
            ),
            27.0,
        )


class HoverActionTests(unittest.TestCase):
    def test_hover_moves_to_selector_center(self):
        page = HoldPage()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(HoldBrowser(page), Path(tmp), logging.getLogger("hover"))
            result = engine.run([{
                "type": "hover",
                "selector": "[class*='styles_displayName__']:visible",
                "timeout_ms": 15000,
            }])[0]
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(page.mouse.moves, [(120.0, 210.0)])
        self.assertEqual(result["data"]["x"], 120.0)
        self.assertEqual(result["data"]["y"], 210.0)

    def test_hover_supports_offset(self):
        page = HoldPage()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(HoldBrowser(page), Path(tmp), logging.getLogger("hover-offset"))
            result = engine.run([{
                "type": "hover",
                "selector": "button[data-testid='profile']:visible",
                "offset": {"x": 15, "y": -10},
                "timeout_ms": 15000,
            }])[0]
        self.assertEqual(page.mouse.moves, [(135.0, 200.0)])
        self.assertEqual(result["data"]["offset"], {"x": 15.0, "y": -10.0})

    def test_hover_supports_iframe_chain(self):
        page = HoldPage()
        with tempfile.TemporaryDirectory() as tmp:
            engine = ActionEngine(HoldBrowser(page), Path(tmp), logging.getLogger("hover-frame"))
            engine.run([{
                "type": "hover",
                "frames": ["iframe#outer", "iframe#inner"],
                "selector": "a[href^='/users/']:visible",
                "timeout_ms": 15000,
            }])
        self.assertEqual(page.scope.frames, ["iframe#outer", "iframe#inner"])
        self.assertEqual(page.scope.selector, "a[href^='/users/']:visible")
        self.assertEqual(page.mouse.moves, [(120.0, 210.0)])


class DebugCursorOverlayTests(unittest.TestCase):
    def test_cursor_overlay_disabled_does_not_touch_page(self):
        from app.actions.context import ScenarioContext

        class Page:
            def __init__(self):
                self.calls = []
            def evaluate(self, *args):
                self.calls.append(args)

        page = Page()

        class Browser:
            pages = [page]

        ctx = ScenarioContext(
            browser_context=Browser(),
            artifact_dir=Path("/tmp"),
            logger=logging.getLogger("cursor-disabled"),
            show_cursor=False,
        )
        ctx.move_debug_cursor(100, 200, page)
        self.assertEqual(page.calls, [])

    def test_cursor_overlay_installs_and_moves(self):
        from app.actions.context import ScenarioContext

        class Page:
            def __init__(self):
                self.calls = []
            def evaluate(self, script, arg=None):
                self.calls.append((script, arg))
                return True

        page = Page()

        class Browser:
            pages = [page]

        ctx = ScenarioContext(
            browser_context=Browser(),
            artifact_dir=Path("/tmp"),
            logger=logging.getLogger("cursor-enabled"),
            show_cursor=True,
        )
        ctx.move_debug_cursor(321.5, 222.25, page)

        self.assertGreaterEqual(len(page.calls), 2)
        move_arg = page.calls[-1][1]
        self.assertEqual(move_arg["cursorId"], "__camoufox_debug_cursor__")
        self.assertEqual(move_arg["x"], 321.5)
        self.assertEqual(move_arg["y"], 222.25)


class LiveDebugCursorTrajectoryTests(unittest.TestCase):
    def test_show_cursor_registers_mousemove_init_script(self):
        from app.actions.context import ScenarioContext

        class Browser:
            pages = []
            def __init__(self):
                self.scripts = []
            def add_init_script(self, script=None):
                self.scripts.append(script)
            def on(self, *args):
                pass

        browser = Browser()
        ScenarioContext(
            browser_context=browser,
            artifact_dir=Path("/tmp"),
            logger=logging.getLogger("cursor-live-init"),
            show_cursor=True,
        )

        self.assertEqual(len(browser.scripts), 1)
        script = browser.scripts[0]
        self.assertIn('document.addEventListener("mousemove"', script)
        self.assertIn('event.clientX', script)
        self.assertIn('event.clientY', script)
        self.assertIn('pointerEvents: "none"', script)
