from __future__ import annotations

import random
import time

from ..runtime import ShutdownRequested
from .base import BaseAction
from .registry import register_action


@register_action
class WaitAction(BaseAction):
    name = "wait"
    def execute(self, ctx, action, index):
        min_s = float(action.get("min", 1))
        max_s = float(action.get("max", min_s))
        duration = random.uniform(min_s, max_s)
        if ctx.runtime is not None:
            if not ctx.runtime.interruptible_wait(duration):
                raise ShutdownRequested(ctx.runtime.shutdown_signal)
        else:
            time.sleep(duration)
        return {"slept_sec": round(duration, 3)}
