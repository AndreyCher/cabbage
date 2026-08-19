from __future__ import annotations

from .base import BaseAction
from .registry import register_action


@register_action
class ScreenshotAction(BaseAction):
    name = "screenshot"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        name = action.get("name") or f"{index:03d}.png"
        path = ctx.artifact_dir / "screenshots" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=action.get("full_page", False))
        return {"path": str(path)}


@register_action
class ClickLinkByIndexAction(BaseAction):
    name = "click_link_by_index"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        selector = action.get("selector", "a[href]")
        links = page.locator(selector)
        count = links.count()
        if count == 0:
            raise RuntimeError(f"No links found for selector: {selector}")
        requested = int(action.get("index", 0))
        idx = min(requested, count - 1)
        href = links.nth(idx).get_attribute("href")
        links.nth(idx).click()
        return {"selector": selector, "index": idx, "href": href, "url": page.url}
