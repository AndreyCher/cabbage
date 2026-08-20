from __future__ import annotations

from .base import BaseAction
from .registry import register_action


@register_action
class PluginCallAction(BaseAction):
    name = "plugin_call"

    def execute(self, ctx, action, index):
        if ctx.plugins is None:
            raise ValueError("Plugin subsystem is not initialized")
        plugin = str(action.get("plugin", "")).strip()
        method = str(action.get("method", "")).strip()
        if not plugin:
            raise ValueError("plugin_call requires 'plugin'")
        if not method:
            raise ValueError("plugin_call requires 'method'")
        params = action.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("plugin_call.params must be an object")
        ctx.logger.info("PLUGIN %03d call plugin=%s method=%s", index, plugin, method)
        result = ctx.plugins.invoke(plugin, method, ctx, params)
        if isinstance(result, dict):
            return {"plugin": plugin, "method": method, **result}
        return {"plugin": plugin, "method": method, "result": result}
