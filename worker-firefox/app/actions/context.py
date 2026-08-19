from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..runtime import FatalActionError, RuntimeContext


@dataclass
class ScenarioContext:
    """Shared state exposed to action modules during one scenario run.

    Keeps the local page registry synchronized with the real browser context so
    tabs opened by the site (target=_blank/window.open) are visible to scenario
    actions just like tabs created through the new_tab action.

    v0.5.11 additionally pumps the Playwright Sync API event loop while waiting
    for a requested tab, preventing site-created page events from being delayed
    until browser shutdown.
    """

    browser_context: Any
    artifact_dir: Path
    logger: Any
    runtime: RuntimeContext | None = None
    plugins: Any | None = None
    show_cursor: bool = False
    pages: list[Any] = field(default_factory=list)
    page: Any | None = None

    def __post_init__(self):
        self.sync_pages()
        # Playwright BrowserContext emits "page" for popups/new tabs created by
        # the web application. Fake/test contexts may not implement .on().
        on = getattr(self.browser_context, "on", None)
        if callable(on):
            on("page", self._on_page)
        self.configure_debug_cursor()

    def _on_page(self, page):
        if page not in self.pages:
            self.pages.append(page)
            self.logger.info("TAB    detected index=%d url=%s", len(self.pages) - 1, getattr(page, "url", ""))
        self.ensure_debug_cursor(page)

    def sync_pages(self):
        """Merge BrowserContext.pages into the scenario page registry."""
        for page in list(getattr(self.browser_context, "pages", []) or []):
            if page not in self.pages:
                self.pages.append(page)
        return self.pages

    def ensure_page(self):
        self.sync_pages()
        if self.page is None:
            if self.pages:
                self.page = self.pages[0]
            else:
                self.page = self.browser_context.new_page()
                self.sync_pages()
                if self.page not in self.pages:
                    self.pages.append(self.page)
        return self.page

    def new_page(self):
        self.page = self.browser_context.new_page()
        self.sync_pages()
        if self.page not in self.pages:
            self.pages.append(self.page)
        self.ensure_debug_cursor(self.page)
        return self.page


    _CURSOR_ID = "__camoufox_debug_cursor__"
    _CURSOR_INIT_SCRIPT = r"""
(() => {
    const cursorId = "__camoufox_debug_cursor__";
    const installedFlag = "__camoufox_debug_cursor_listener_installed__";

    const ensureCursor = () => {
        const root = document.documentElement || document.body;
        if (!root) return null;

        let el = document.getElementById(cursorId);
        if (!el) {
            el = document.createElement("div");
            el.id = cursorId;
            el.setAttribute("aria-hidden", "true");
            Object.assign(el.style, {
                position: "fixed",
                left: "0px",
                top: "0px",
                width: "14px",
                height: "14px",
                borderRadius: "50%",
                background: "#ff0000",
                boxShadow: "0 0 0 2px rgba(255,255,255,.85)",
                transform: "translate(-50%, -50%)",
                pointerEvents: "none",
                zIndex: "2147483647",
                display: "none"
            });
            root.appendChild(el);
        }
        return el;
    };

    if (!window[installedFlag]) {
        window[installedFlag] = true;

        document.addEventListener("mousemove", (event) => {
            const el = ensureCursor();
            if (!el) return;
            el.style.left = `${event.clientX}px`;
            el.style.top = `${event.clientY}px`;
            el.style.display = "block";
        }, true);

        document.addEventListener("mouseleave", () => {
            const el = document.getElementById(cursorId);
            if (el) el.style.display = "none";
        }, true);
    }

    ensureCursor();
})();
"""

    def configure_debug_cursor(self):
        """Install live mousemove tracking for all future documents/frames."""
        if not self.show_cursor:
            return

        add_init_script = getattr(self.browser_context, "add_init_script", None)
        if callable(add_init_script):
            try:
                add_init_script(script=self._CURSOR_INIT_SCRIPT)
            except TypeError:
                # Compatibility with simple/fake contexts and older wrappers.
                add_init_script(self._CURSOR_INIT_SCRIPT)
            except Exception as exc:
                self.logger.warning("CURSOR init-script registration failed: %s", exc)

        # Existing documents were created before add_init_script registration.
        for page in list(self.pages):
            self.ensure_debug_cursor(page)

    def ensure_debug_cursor(self, page=None):
        """Install the live cursor overlay/listener in the current document."""
        if not self.show_cursor:
            return False
        page = page or self.ensure_page()
        try:
            page.evaluate(self._CURSOR_INIT_SCRIPT)
            return True
        except Exception:
            # Navigation may currently be between documents. The init script
            # will install automatically in the next document.
            return False

    def move_debug_cursor(self, x: float, y: float, page=None):
        """Fallback endpoint update; live movement comes from DOM mousemove."""
        if not self.show_cursor:
            return
        page = page or self.ensure_page()
        if not self.ensure_debug_cursor(page):
            return
        try:
            page.evaluate(
                """({cursorId, x, y}) => {
                    const el = document.getElementById(cursorId);
                    if (!el) return false;
                    el.style.left = `${x}px`;
                    el.style.top = `${y}px`;
                    el.style.display = "block";
                    return true;
                }""",
                {"cursorId": self._CURSOR_ID, "x": float(x), "y": float(y)},
            )
        except Exception:
            pass

    def _resolve_page_index(self, index: int | None = None, target: str | None = None) -> int:
        if target is not None:
            normalized = str(target).strip().lower()
            if normalized in {"last", "newest"}:
                if not self.pages:
                    raise IndexError("No browser tabs are available")
                return len(self.pages) - 1
            if normalized in {"first", "oldest"}:
                return 0
            raise ValueError("switch_tab.target must be one of: first, oldest, last, newest")
        if index is None:
            raise ValueError("switch_tab requires either 'index' or 'target'")
        return int(index)

    def switch_page(self, index: int | None = None, target: str | None = None, timeout_ms: int = 15000):
        deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
        while True:
            self.sync_pages()
            try:
                resolved_index = self._resolve_page_index(index=index, target=target)
                if -len(self.pages) <= resolved_index < len(self.pages):
                    self.page = self.pages[resolved_index]
                    self.page.bring_to_front()
                    self.ensure_debug_cursor(self.page)
                    return self.page, resolved_index
            except IndexError:
                pass

            if time.monotonic() >= deadline:
                requested = f"target={target!r}" if target is not None else f"index={index}"
                raise FatalActionError(
                    f"Browser tab {requested} did not become available within {int(timeout_ms)} ms; known_tabs={len(self.pages)}",
                    reason="tab_not_available",
                    details={
                        "requested_tab": requested,
                        "known_tabs": len(self.pages),
                        "timeout_ms": int(timeout_ms),
                    },
                )
            # Do not use a plain time.sleep() here when a Playwright page is
            # available. The Sync API dispatches BrowserContext/page events while
            # executing Playwright calls. A blocking Python sleep can therefore
            # leave a newly opened browser tab visible in noVNC while the
            # browser_context.on("page") callback is not delivered to Python.
            current_page = self.page
            wait_for_timeout = getattr(current_page, "wait_for_timeout", None)
            if callable(wait_for_timeout):
                wait_for_timeout(50)
            else:
                time.sleep(0.05)
