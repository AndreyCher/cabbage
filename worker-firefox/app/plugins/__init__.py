"""Third-party plugin framework for Firefox worker."""

from .base import BasePlugin, PluginError
from .manager import PluginManager, PluginSpec

__all__ = ["BasePlugin", "PluginError", "PluginManager", "PluginSpec"]
