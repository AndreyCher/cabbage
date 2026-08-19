"""Modular scenario action framework.

Built-in action modules are discovered automatically. Adding a new module under
``app/actions`` with one or more ``@register_action`` classes does not require
changes to ActionEngine or to this package initializer.
"""

from __future__ import annotations

import importlib
import pkgutil

from .base import BaseAction
from .context import ScenarioContext
from .registry import ActionRegistry, register_action, registry

_CORE_MODULES = {"base", "context", "engine", "registry"}


def _load_action_modules() -> None:
    prefix = __name__ + "."
    for module in pkgutil.iter_modules(__path__):
        if module.name.startswith("_") or module.name in _CORE_MODULES:
            continue
        importlib.import_module(prefix + module.name)


_load_action_modules()

from .engine import ActionEngine

__all__ = [
    "ActionEngine",
    "ActionRegistry",
    "BaseAction",
    "ScenarioContext",
    "register_action",
    "registry",
]
