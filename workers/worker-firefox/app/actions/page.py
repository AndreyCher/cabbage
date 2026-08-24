from __future__ import annotations

from ..runtime import FatalActionError
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
            raise FatalActionError(
                f"Action {index:03d} could not find any links matching selector {selector!r}.",
                reason="selector_no_matches",
                details={"selector": selector, "matched_count": 0, "requested_index": int(action.get("index", 0))},
            )
        requested = int(action.get("index", 0))
        if requested < 0 or requested >= count:
            raise FatalActionError(
                f"Action {index:03d} requested link index {requested}, but selector {selector!r} matched {count} links (valid indexes: 0–{count - 1}).",
                reason="link_index_out_of_range",
                details={"selector": selector, "matched_count": count, "requested_index": requested},
            )
        idx = requested
        href = links.nth(idx).get_attribute("href")
        links.nth(idx).click()
        return {"selector": selector, "index": idx, "href": href, "url": page.url}
