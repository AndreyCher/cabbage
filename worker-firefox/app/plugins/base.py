from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PluginError(RuntimeError):
    """Controlled plugin configuration/loading/invocation failure."""

    def __init__(self, message: str, *, reason: str = "plugin_error", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason = reason
        self.details = details or {}


class BasePlugin(ABC):
    """Stable adapter contract for optional third-party browser libraries."""

    name: str = ""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = dict(config or {})

    def setup(self, ctx) -> None:
        """Optional one-time setup before the first invocation in a run."""

    @abstractmethod
    def invoke(self, method: str, ctx, params: dict[str, Any]) -> Any:
        """Invoke one plugin operation and return JSON-serializable data."""

    def teardown(self, ctx) -> None:
        """Optional best-effort teardown during run finalization."""
