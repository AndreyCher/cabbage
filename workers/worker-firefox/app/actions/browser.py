from __future__ import annotations

from .base import BaseAction
from .registry import register_action


@register_action
class OpenAction(BaseAction):
    name = "open"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        response = page.goto(action["url"], wait_until=action.get("wait_until", "domcontentloaded"), timeout=action.get("timeout_ms", 60000))
        ctx.ensure_debug_cursor(page)
        return {"url": page.url, "status": response.status if response else None}


@register_action
class NewTabAction(BaseAction):
    name = "new_tab"
    def execute(self, ctx, action, index):
        page = ctx.new_page()
        if action.get("url"):
            page.goto(action["url"], wait_until=action.get("wait_until", "domcontentloaded"), timeout=action.get("timeout_ms", 60000))
        ctx.ensure_debug_cursor(page)
        ctx.sync_pages()
        return {"tab_index": ctx.pages.index(page), "url": page.url}


@register_action
class SwitchTabAction(BaseAction):
    name = "switch_tab"
    def execute(self, ctx, action, index):
        page, resolved_index = ctx.switch_page(
            index=action.get("index"),
            target=action.get("target"),
            timeout_ms=action.get("timeout_ms", 15000),
        )
        return {"tab_index": resolved_index, "url": page.url}


@register_action
class GoBackAction(BaseAction):
    name = "go_back"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        response = page.go_back(wait_until=action.get("wait_until", "domcontentloaded"), timeout=action.get("timeout_ms", 60000))
        ctx.ensure_debug_cursor(page)
        return {"url": page.url, "status": response.status if response else None}
