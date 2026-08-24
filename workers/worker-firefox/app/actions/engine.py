from __future__ import annotations

import signal
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..runtime import FatalActionError, RuntimeContext, ShutdownRequested
from ..plugins.base import PluginError
from .context import ScenarioContext
from .registry import registry


class ActionEngine:
    """Scenario orchestrator. Concrete browser behavior lives in action modules."""

    WATCHDOG_GRACE_MS = 2000
    DEFAULT_ACTION_TIMEOUT_MS = 30000
    WATCHDOG_EXEMPT_ACTIONS = {"wait", "wait_input"}

    def __init__(self, context, artifact_dir: Path, logger, continue_on_error_default: bool = False, runtime: RuntimeContext | None = None, plugins=None, show_cursor: bool = False):
        self.ctx = ScenarioContext(
            browser_context=context,
            artifact_dir=artifact_dir,
            logger=logger,
            runtime=runtime,
            plugins=plugins,
            show_cursor=bool(show_cursor),
        )
        self.continue_on_error_default = bool(continue_on_error_default)

    @property
    def context(self):
        return self.ctx.browser_context

    @property
    def artifact_dir(self):
        return self.ctx.artifact_dir

    @property
    def logger(self):
        return self.ctx.logger

    @property
    def runtime(self):
        return self.ctx.runtime

    @property
    def pages(self):
        return self.ctx.pages

    @pages.setter
    def pages(self, value):
        self.ctx.pages = value

    @property
    def page(self):
        return self.ctx.page

    @page.setter
    def page(self, value):
        self.ctx.page = value

    def ensure_page(self):
        return self.ctx.ensure_page()

    @classmethod
    def _watchdog_timeout_sec(cls, action: dict[str, Any], action_type: str | None = None) -> float | None:
        """Return a hard engine-level timeout for one action.

        action_timeout_ms explicitly controls the watchdog. For browser actions
        that already expose timeout_ms, the engine automatically adds a small
        grace period so a stuck Playwright/Camoufox IPC call cannot hang forever.
        wait/wait_input keep their own explicit timing semantics. Other actions
        receive a 30s engine-level watchdog even if they do not declare a timeout,
        so a stuck browser IPC call cannot leave the scenario running forever.
        """
        if "action_timeout_ms" in action:
            timeout_ms = int(action["action_timeout_ms"])
            if timeout_ms <= 0:
                raise ValueError("action_timeout_ms must be greater than 0")
            return timeout_ms / 1000.0
        if "timeout_ms" in action:
            timeout_ms = int(action["timeout_ms"])
            if timeout_ms <= 0:
                raise ValueError("timeout_ms must be greater than 0")
            # mouse_press can intentionally hold the mouse button for a long
            # time after locating/moving to the target. That intentional hold
            # must not be mistaken for a stuck browser action.
            intentional_hold_ms = 0
            if action_type == "mouse_press":
                intentional_hold_ms = int(action.get("hold_ms", 1000))
                if intentional_hold_ms < 0:
                    raise ValueError("mouse_press.hold_ms must be >= 0")
            return (timeout_ms + intentional_hold_ms + cls.WATCHDOG_GRACE_MS) / 1000.0
        if action_type in cls.WATCHDOG_EXEMPT_ACTIONS:
            return None
        return cls.DEFAULT_ACTION_TIMEOUT_MS / 1000.0

    @contextmanager
    def _action_watchdog(self, action: dict[str, Any], index: int, action_type: str):
        timeout_sec = self._watchdog_timeout_sec(action, action_type)
        if timeout_sec is None:
            yield
            return

        # signal.setitimer works only in the main thread. The scenario engine is
        # currently run there; retain a safe fallback in case that changes.
        if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
            self.logger.warning(
                "WATCHDOG %03d %-20s unavailable outside main thread; native timeout only",
                index,
                action_type,
            )
            yield
            return

        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)

        def _timeout_handler(_signum, _frame):
            raise FatalActionError(
                f"Action '{action_type}' exceeded hard timeout of {timeout_sec:.3f}s.",
                reason="action_timeout",
                details={
                    "timeout_sec": round(timeout_sec, 3),
                    "timeout_ms": action.get("timeout_ms"),
                    "action_timeout_ms": action.get("action_timeout_ms"),
                },
            )

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout_sec)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            if previous_timer[0] > 0:
                signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])

    def run(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for index, action in enumerate(actions, start=1):
            if self.runtime is not None:
                self.runtime.raise_if_shutdown_requested()
            action_type = action["type"]
            started = time.time()
            if self.runtime is not None:
                self.runtime.set_action(index)
            # Log unresolved action so runtime credentials/OTP values never enter run.log.
            self.logger.info("ACTION %03d %-20s %s", index, action_type, action)
            try:
                handler = registry.get(action_type)
                if handler is None:
                    raise ValueError(f"Unsupported action type: {action_type}")

                resolved_action = self.runtime.resolve_value(action) if self.runtime is not None else action
                with self._action_watchdog(resolved_action, index, action_type):
                    data = handler.execute(self.ctx, resolved_action, index)
                if self.runtime is not None:
                    self.runtime.raise_if_shutdown_requested()
                status = "PASS"
                self.logger.info("PASS   %03d %-20s", index, action_type)
            except ShutdownRequested:
                self.logger.info("STOP   %03d %-20s shutdown requested", index, action_type)
                raise
            except PlaywrightTimeoutError as exc:
                status = "FAIL"
                timeout_ms = int(action.get("timeout_ms", self.DEFAULT_ACTION_TIMEOUT_MS))
                selector = action.get("selector")
                if selector:
                    message = f"{action_type.upper()} {index:03d} failed: element {selector!r} was not visible within {timeout_ms} ms"
                else:
                    message = f"{action_type.upper()} {index:03d} failed: Playwright timeout after {timeout_ms} ms"
                data = {
                    "error": message,
                    "reason": "playwright_timeout",
                    "timeout_ms": timeout_ms,
                }
                if selector:
                    data["selector"] = selector
                self.logger.error(message)
                continue_on_error = bool(action.get("continue_on_error", self.continue_on_error_default))
                results.append(self._result(index, action, status, started, data))
                if continue_on_error:
                    self.logger.warning("CONTINUE %03d %-20s after controlled Playwright timeout", index, action_type)
                    continue
                raise FatalActionError(
                    message,
                    reason="playwright_timeout",
                    details={**data, "failed_action": index, "action_type": action_type},
                ) from None
            except PluginError as exc:
                status = "FAIL"
                data = {"error": str(exc), "reason": exc.reason, **exc.details}
                plugin_name = exc.details.get("plugin") or action.get("plugin")
                method_name = exc.details.get("method") or action.get("method")
                self.logger.error(
                    "FAIL   %03d %-20s reason=%s plugin=%s method=%s message=%s",
                    index, action_type, exc.reason, plugin_name, method_name, str(exc),
                )
                continue_on_error = bool(action.get("continue_on_error", self.continue_on_error_default))
                results.append(self._result(index, action, status, started, data))
                if continue_on_error:
                    self.logger.warning("CONTINUE %03d %-20s after controlled plugin failure", index, action_type)
                    continue
                raise FatalActionError(
                    str(exc),
                    reason=exc.reason,
                    details={**exc.details, "failed_action": index, "action_type": action_type},
                ) from None
            except Exception as exc:
                status = "FAIL"
                if isinstance(exc, FatalActionError):
                    data = {"error": str(exc), "reason": exc.reason, **exc.details}
                    self.logger.error(
                        "FAIL   %03d %-20s reason=%s message=%s",
                        index, action_type, exc.reason, str(exc),
                    )
                else:
                    message = f"Action {index:03d} {action_type!r} failed: {str(exc) or type(exc).__name__}"
                    data = {"error": message, "reason": "action_failed", "error_type": type(exc).__name__}
                    self.logger.exception("FAIL   %03d %-20s", index, action_type)

                continue_on_error = bool(action.get("continue_on_error", self.continue_on_error_default))
                results.append(self._result(index, action, status, started, data))
                if isinstance(exc, FatalActionError):
                    exc.details.setdefault("failed_action", index)
                    exc.details.setdefault("action_type", action_type)
                    raise
                if continue_on_error:
                    self.logger.warning("CONTINUE %03d %-20s after failure", index, action_type)
                    continue
                raise FatalActionError(
                    message,
                    reason="action_failed",
                    details={**data, "failed_action": index, "action_type": action_type},
                ) from exc

            results.append(self._result(index, action, status, started, data))
        return results

    @staticmethod
    def _result(index, action, status, started, data):
        return {
            "index": index,
            "type": action["type"],
            "status": status,
            "duration_sec": round(time.time() - started, 3),
            "data": data,
        }
