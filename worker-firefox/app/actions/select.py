from __future__ import annotations

from .base import BaseAction
from .registry import register_action


@register_action
class SelectAction(BaseAction):
    """Select an option from native <select> or a custom combobox/listbox.

    Native selects use Playwright ``select_option``. Custom dropdowns are
    interacted with using the existing page/locator APIs, keeping the action
    isolated from ActionEngine.
    """

    name = "select"

    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        selector = action["selector"]
        timeout = int(action.get("timeout_ms", 15000))
        method = str(action.get("method", "auto")).lower()
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=timeout)

        provided = [key for key in ("value", "label", "index") if key in action]
        if len(provided) != 1:
            raise ValueError("select requires exactly one of 'value', 'label', or 'index'")

        if method not in {"auto", "native", "custom"}:
            raise ValueError("select.method must be one of: auto, native, custom")

        if method == "auto":
            try:
                tag_name = str(locator.evaluate("el => el.tagName")).lower()
            except Exception:
                tag_name = ""
            method = "native" if tag_name == "select" else "custom"

        if method == "native":
            kwargs = {}
            if "value" in action:
                kwargs["value"] = str(action["value"])
            elif "label" in action:
                kwargs["label"] = str(action["label"])
            else:
                kwargs["index"] = int(action["index"])
            selected = locator.select_option(**kwargs, timeout=timeout)
            return {
                "selector": selector,
                "method": "native",
                "selected": selected,
                "by": provided[0],
                "target": action[provided[0]],
            }

        # Custom dropdown / combobox. The trigger itself is clicked first.
        locator.click(timeout=timeout)
        exact = bool(action.get("exact", True))
        option_selector = action.get("option_selector")

        if option_selector:
            option = page.locator(str(option_selector))
            if "label" in action:
                option = option.filter(has_text=str(action["label"]))
            elif "value" in action:
                value = str(action["value"]).replace('"', '\\"')
                option = page.locator(
                    f'{option_selector}[data-value="{value}"], '
                    f'{option_selector}[value="{value}"]'
                )
            option = option.first
        elif "label" in action:
            option = page.get_by_role("option", name=str(action["label"]), exact=exact).first
        elif "value" in action:
            value = str(action["value"]).replace('"', '\\"')
            option = page.locator(
                f'[role="option"][data-value="{value}"], '
                f'[role="option"][value="{value}"], '
                f'[data-value="{value}"][role="menuitem"]'
            ).first
        else:
            option = page.locator('[role="option"]',).nth(int(action["index"]))

        option.wait_for(state="visible", timeout=timeout)
        option.click(timeout=timeout)
        return {
            "selector": selector,
            "method": "custom",
            "by": provided[0],
            "target": action[provided[0]],
            "option_selector": option_selector,
        }
