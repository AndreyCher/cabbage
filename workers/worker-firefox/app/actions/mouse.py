from __future__ import annotations

import random
import time

from .base import BaseAction
from .registry import register_action


@register_action
class ScrollAction(BaseAction):
    name = "scroll"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        if "delta_y" in action:
            delta_y = int(action["delta_y"])
        else:
            min_px, max_px = action.get("distance", [350, 900])
            delta_y = random.randint(int(min_px), int(max_px))
            if action.get("direction", "down") == "up":
                delta_y = -delta_y
        delta_x = int(action.get("delta_x", 0))
        page.mouse.wheel(delta_x, delta_y)
        return {"delta_x": delta_x, "delta_y": delta_y}


@register_action
class MouseMoveAction(BaseAction):
    name = "mouse_move"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        viewport = page.evaluate("() => ({w: innerWidth, h: innerHeight})")
        requested_x = int(action["x"])
        requested_y = int(action["y"])
        clamp = bool(action.get("clamp_to_viewport", True))
        if clamp:
            max_x = max(0, int(viewport["w"]) - 1)
            max_y = max(0, int(viewport["h"]) - 1)
            x = min(max(requested_x, 0), max_x)
            y = min(max(requested_y, 0), max_y)
        else:
            x, y = requested_x, requested_y
        # Camoufox humanize owns the trajectory.  Supplying Playwright `steps`
        # on top of Camoufox's native cursor humanization can stall v152 builds.
        legacy_duration = action.get("duration")
        legacy_steps = action.get("steps")
        if legacy_duration is not None or legacy_steps is not None:
            ctx.logger.info(
                "MOUSE  %03d native_humanize legacy duration/steps ignored",
                index,
            )
        page.mouse.move(x, y)
        ctx.move_debug_cursor(x, y, page)
        return {
            "requested_x": requested_x,
            "requested_y": requested_y,
            "x": x,
            "y": y,
            "movement": "camoufox_humanize",
            "legacy_duration_ignored": legacy_duration,
            "legacy_steps_ignored": legacy_steps,
            "clamped": x != requested_x or y != requested_y,
            "viewport": viewport,
        }


@register_action
class MouseMoveRandomAction(BaseAction):
    name = "mouse_move_random"
    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        viewport = page.evaluate("() => ({w: innerWidth, h: innerHeight})")
        count = int(action.get("count", 3))
        if count < 1 or count > 100:
            raise ValueError("mouse_move_random.count must be between 1 and 100")
        method = str(action.get("method", "dom"))
        if method not in {"dom", "native"}:
            raise ValueError("mouse_move_random.method must be one of: dom, native")
        points = []
        for _ in range(count):
            x = random.randint(20, max(21, int(viewport["w"]) - 20))
            y = random.randint(20, max(21, int(viewport["h"]) - 20))
            delay_ms = random.randint(150, 650)
            points.append({"x": x, "y": y, "delay_ms": delay_ms})
        if method == "native":
            for point in points:
                page.mouse.move(point["x"], point["y"])
                ctx.move_debug_cursor(point["x"], point["y"], page)
                time.sleep(point["delay_ms"] / 1000.0)
        else:
            # Camoufox v152 can indefinitely block a synchronous native
            # page.mouse.move call. Random movement is non-functional behavior,
            # so dispatch bounded DOM mouse events instead of risking the whole run.
            page.evaluate(
                """async (points) => {
                    for (const point of points) {
                        const target = document.elementFromPoint(point.x, point.y) || document;
                        target.dispatchEvent(new MouseEvent('mousemove', {
                            bubbles: true, cancelable: true, view: window,
                            clientX: point.x, clientY: point.y,
                        }));
                        await new Promise(resolve => setTimeout(resolve, point.delay_ms));
                    }
                }""",
                points,
            )
        return {"points": [[point["x"], point["y"]] for point in points], "movement": f"{method}_random"}


@register_action
class ClickAction(BaseAction):
    name = "click"

    @staticmethod
    def _remaining_ms(deadline: float, selector: str) -> int:
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError(f"Click timeout expired before completing selector: {selector}")
        return max(1, remaining)

    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        selector = action["selector"]
        timeout_ms = int(action.get("timeout_ms", 15000))
        if timeout_ms <= 0:
            raise ValueError("click.timeout_ms must be greater than 0")
        deadline = time.monotonic() + timeout_ms / 1000.0
        method = action.get("method", "locator")
        locator = page.locator(selector).first

        ctx.logger.info("CLICK  %03d wait_visible selector=%s", index, selector)
        locator.wait_for(state="visible", timeout=self._remaining_ms(deadline, selector))
        ctx.logger.info("CLICK  %03d visible", index)

        if method == "mouse":
            ctx.logger.info("CLICK  %03d bounding_box", index)
            box = locator.bounding_box(timeout=self._remaining_ms(deadline, selector))
            if box is None:
                raise RuntimeError(f"Unable to determine bounding box for selector: {selector}")
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            if "steps" in action:
                ctx.logger.info("CLICK  %03d native_humanize legacy steps ignored", index)
            ctx.logger.info("CLICK  %03d mouse_move x=%.2f y=%.2f native_humanize", index, x, y)
            page.mouse.move(x, y)
            ctx.move_debug_cursor(x, y, page)
            ctx.logger.info("CLICK  %03d mouse_click button=%s", index, action.get("button", "left"))
            page.mouse.click(x, y, button=action.get("button", "left"))
            return {"selector": selector, "method": "mouse", "x": round(x, 2), "y": round(y, 2), "movement": "camoufox_humanize", "legacy_steps_ignored": action.get("steps"), "url": page.url}

        if method != "locator":
            raise ValueError(f"Unsupported click method: {method}. Supported methods: locator, mouse")

        ctx.logger.info("CLICK  %03d locator_click", index)
        locator.click(
            timeout=self._remaining_ms(deadline, selector),
            force=bool(action.get("force", False)),
        )
        return {"selector": selector, "method": "locator", "url": page.url}


@register_action
class MousePressAction(BaseAction):
    """Physically press and hold a mouse button.

    The target may be a DOM element (optionally inside one or more iframes) or
    absolute viewport coordinates. Camoufox remains responsible for the native
    humanized pointer trajectory.
    """

    name = "mouse_press"

    @staticmethod
    def _remaining_ms(deadline: float, target: str) -> int:
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError(f"mouse_press timeout expired before reaching target: {target}")
        return max(1, remaining)

    @staticmethod
    def _frame_chain(action):
        if "frames" in action and action["frames"] is not None:
            frames = action["frames"]
            if not isinstance(frames, list) or not all(isinstance(item, str) and item for item in frames):
                raise ValueError("mouse_press.frames must be a non-empty list of iframe selectors")
            return frames
        if action.get("frame_selector"):
            return [str(action["frame_selector"])]
        return []

    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        has_selector = bool(action.get("selector"))
        has_position = action.get("position") is not None
        if has_selector == has_position:
            raise ValueError("mouse_press requires exactly one of 'selector' or 'position'")

        button = str(action.get("button", "left"))
        if button not in {"left", "right", "middle"}:
            raise ValueError("mouse_press.button must be one of: left, right, middle")

        hold_ms = int(action.get("hold_ms", 1000))
        timeout_ms = int(action.get("timeout_ms", 15000))
        if hold_ms < 0:
            raise ValueError("mouse_press.hold_ms must be >= 0")
        if timeout_ms <= 0:
            raise ValueError("mouse_press.timeout_ms must be greater than 0")

        deadline = time.monotonic() + timeout_ms / 1000.0
        frames = self._frame_chain(action)
        offset = action.get("offset") or {}
        offset_x = float(offset.get("x", 0))
        offset_y = float(offset.get("y", 0))

        if has_selector:
            selector = str(action["selector"])
            scope = page
            for frame_selector in frames:
                scope = scope.frame_locator(frame_selector)
            locator = scope.locator(selector).first
            ctx.logger.info(
                "MPRESS %03d wait_visible selector=%s frames=%s",
                index, selector, frames or "main",
            )
            locator.wait_for(
                state="visible",
                timeout=self._remaining_ms(deadline, selector),
            )
            box = locator.bounding_box(
                timeout=self._remaining_ms(deadline, selector),
            )
            if box is None:
                raise RuntimeError(f"Unable to determine bounding box for selector: {selector}")
            x = box["x"] + box["width"] / 2 + offset_x
            y = box["y"] + box["height"] / 2 + offset_y
            target_description = selector
        else:
            position = action["position"]
            if not isinstance(position, dict) or "x" not in position or "y" not in position:
                raise ValueError("mouse_press.position must contain x and y")
            if frames:
                raise ValueError("mouse_press frames/frame_selector cannot be used with absolute position")
            x = float(position["x"]) + offset_x
            y = float(position["y"]) + offset_y
            target_description = f"position({x:.2f},{y:.2f})"

        ctx.logger.info(
            "MPRESS %03d mouse_move x=%.2f y=%.2f native_humanize",
            index, x, y,
        )
        page.mouse.move(x, y)
        ctx.move_debug_cursor(x, y, page)

        ctx.logger.info(
            "MPRESS %03d mouse_down button=%s hold_ms=%d",
            index, button, hold_ms,
        )
        pressed = False
        try:
            page.mouse.down(button=button)
            pressed = True
            if hold_ms:
                # Use Playwright-aware waiting rather than Python sleep so page
                # and frame events continue to be dispatched while held.
                page.wait_for_timeout(hold_ms)
        finally:
            if pressed:
                ctx.logger.info("MPRESS %03d mouse_up button=%s", index, button)
                page.mouse.up(button=button)

        return {
            "selector": action.get("selector"),
            "position": action.get("position"),
            "frames": frames,
            "button": button,
            "hold_ms": hold_ms,
            "x": round(x, 2),
            "y": round(y, 2),
            "offset": {"x": offset_x, "y": offset_y},
            "movement": "camoufox_humanize",
            "target": target_description,
            "url": page.url,
        }


@register_action
class HoverAction(BaseAction):
    """Move the physical Camoufox mouse pointer over any selector target."""

    name = "hover"

    @staticmethod
    def _remaining_ms(deadline: float, selector: str) -> int:
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise TimeoutError(f"hover timeout expired before reaching selector: {selector}")
        return max(1, remaining)

    @staticmethod
    def _frame_chain(action):
        if "frames" in action and action["frames"] is not None:
            frames = action["frames"]
            if not isinstance(frames, list) or not frames or not all(isinstance(item, str) and item for item in frames):
                raise ValueError("hover.frames must be a non-empty list of iframe selectors")
            return frames
        if action.get("frame_selector"):
            return [str(action["frame_selector"])]
        return []

    def execute(self, ctx, action, index):
        page = ctx.ensure_page()
        selector = str(action["selector"])
        timeout_ms = int(action.get("timeout_ms", 15000))
        if timeout_ms <= 0:
            raise ValueError("hover.timeout_ms must be greater than 0")

        offset = action.get("offset") or {}
        offset_x = float(offset.get("x", 0))
        offset_y = float(offset.get("y", 0))
        frames = self._frame_chain(action)
        deadline = time.monotonic() + timeout_ms / 1000.0

        scope = page
        for frame_selector in frames:
            scope = scope.frame_locator(frame_selector)

        locator = scope.locator(selector).first
        ctx.logger.info(
            "HOVER  %03d wait_visible selector=%s frames=%s",
            index, selector, frames or "main",
        )
        locator.wait_for(
            state="visible",
            timeout=self._remaining_ms(deadline, selector),
        )
        box = locator.bounding_box(
            timeout=self._remaining_ms(deadline, selector),
        )
        if box is None:
            raise RuntimeError(f"Unable to determine bounding box for selector: {selector}")

        x = box["x"] + box["width"] / 2 + offset_x
        y = box["y"] + box["height"] / 2 + offset_y

        ctx.logger.info(
            "HOVER  %03d mouse_move x=%.2f y=%.2f native_humanize",
            index, x, y,
        )
        page.mouse.move(x, y)
        ctx.move_debug_cursor(x, y, page)

        return {
            "selector": selector,
            "frames": frames,
            "x": round(x, 2),
            "y": round(y, 2),
            "offset": {"x": offset_x, "y": offset_y},
            "movement": "camoufox_humanize",
            "url": page.url,
        }
