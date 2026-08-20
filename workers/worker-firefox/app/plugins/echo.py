from __future__ import annotations

from typing import Any

from .base import BasePlugin, PluginError


class EchoPlugin(BasePlugin):
    """Dependency-free reference adapter used to validate the plugin contract."""

    name = "echo"

    def invoke(self, method: str, ctx, params: dict[str, Any]) -> Any:
        if method == "echo":
            return {"echo": params}
        if method == "page_url":
            page = ctx.ensure_page()
            return {"url": page.url}
        raise PluginError(
            f"Unsupported echo plugin method: {method}",
            reason="plugin_method_not_supported",
            details={"method": method},
        )
