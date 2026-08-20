from __future__ import annotations

from .base import BaseAction
from .registry import register_action


@register_action
class TypeAction(BaseAction):
    name = "type"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        locator = page.locator(action["selector"]).first
        locator.wait_for(state="visible", timeout=action.get("timeout_ms", 15000))
        if action.get("clear", True):
            locator.fill("")
        locator.type(action["text"], delay=action.get("delay_ms", 70))
        return {"selector": action["selector"], "chars": len(action["text"])}


@register_action
class PressAction(BaseAction):
    name = "press"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        page.locator(action["selector"]).first.press(action.get("key", "Enter"))
        return {"selector": action["selector"], "key": action.get("key", "Enter")}
