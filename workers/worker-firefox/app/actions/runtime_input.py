from __future__ import annotations

from ..runtime import FatalActionError
from .base import BaseAction
from .registry import register_action


@register_action
class WaitInputAction(BaseAction):
    name = "wait_input"
    def execute(self, ctx, action, index):
        if ctx.runtime is None:
            raise RuntimeError("wait_input requires RuntimeContext")
        key = str(action["key"])
        timeout_sec = float(action.get("timeout_sec", 600))
        if timeout_sec <= 0:
            raise ValueError("wait_input.timeout_sec must be greater than 0")
        on_timeout = str(action.get("on_timeout", "fail"))
        if on_timeout not in {"fail", "continue", "default"}:
            raise ValueError("wait_input.on_timeout must be one of: fail, continue, default")
        ctx.logger.info("WAITING INPUT key=%s timeout=%ss", key, timeout_sec)
        received, _value = ctx.runtime.wait_for_input(key, timeout_sec)
        if received:
            if bool(action.get("consume", False)):
                ctx.runtime.consume_input(key)
            ctx.logger.info("INPUT RECEIVED key=%s", key)
            return {"key": key, "received": True}
        if on_timeout == "continue":
            ctx.logger.warning("INPUT TIMEOUT key=%s; continuing by policy", key)
            return {"key": key, "received": False, "timeout": True, "policy": "continue"}
        if on_timeout == "default":
            if "default" not in action:
                raise ValueError("wait_input with on_timeout=default requires default")
            ctx.runtime.set_default_input(key, action["default"])
            ctx.logger.warning("INPUT TIMEOUT key=%s; default value installed", key)
            return {"key": key, "received": False, "timeout": True, "policy": "default"}
        ctx.logger.error("TIMEOUT %03d wait_input key=%s timeout=%ss; required data not received", index, key, timeout_sec)
        raise FatalActionError(
            "Required runtime input was not received before timeout.",
            reason="timeout_data_not_received",
            details={"input_key": key, "timeout_sec": timeout_sec},
        )
