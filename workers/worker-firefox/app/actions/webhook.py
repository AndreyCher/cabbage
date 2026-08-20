from __future__ import annotations

import time
from typing import Any

import requests

from ..runtime import FatalActionError
from .base import BaseAction
from .registry import register_action


@register_action
class WebhookAction(BaseAction):
    name = "webhook"

    def execute(self, ctx, action: dict[str, Any], index: int):
        if ctx.runtime is None:
            raise RuntimeError("webhook requires RuntimeContext")

        url = str(action["url"])
        method = str(action.get("method", "POST")).upper()
        timeout_ms = int(action.get("timeout_ms", 10000))
        retries = int(action.get("retries", 0))
        save_as = str(action.get("save_as", "response"))
        on_error = str(action.get("on_error", "fail")).lower()
        if timeout_ms <= 0 or retries < 0:
            raise ValueError("webhook timeout_ms must be > 0 and retries must be >= 0")
        if on_error not in {"fail", "continue"}:
            raise ValueError("webhook.on_error must be fail or continue")

        kwargs: dict[str, Any] = {"timeout": timeout_ms / 1000.0}
        for key in ("headers", "params", "json", "data"):
            if key in action:
                kwargs[key] = action[key]

        last_error: Exception | None = None
        for attempt in range(1, retries + 2):
            try:
                ctx.logger.info("WEBHOOK %03d %s %s attempt=%d/%d", index, method, url, attempt, retries + 1)
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "json" in content_type:
                    payload: Any = response.json()
                else:
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = response.text
                ctx.runtime.set_webhook_result(save_as, payload)
                ctx.logger.info("WEBHOOK %03d response status=%d saved_as=%s", index, response.status_code, save_as)
                return {"status_code": response.status_code, "save_as": save_as, "attempt": attempt}
            except requests.RequestException as exc:
                last_error = exc
                if attempt <= retries:
                    ctx.logger.warning("WEBHOOK %03d request failed attempt=%d; retrying: %s", index, attempt, exc)
                    time.sleep(min(0.25 * attempt, 1.0))
                    continue
                break

        message = f"Webhook {method} {url} failed after {retries + 1} attempt(s): {last_error}"
        if on_error == "continue":
            ctx.logger.error("WEBHOOK %03d %s", index, message)
            return {"error": str(last_error), "continued": True, "save_as": save_as}
        raise FatalActionError(message, reason="webhook_failed", details={"url": url, "method": method, "attempts": retries + 1})
