from __future__ import annotations

from typing import Type

from .base import BaseAction


class ActionRegistry:
    def __init__(self):
        self._actions: dict[str, BaseAction] = {}

    def register(self, action_cls: Type[BaseAction]) -> Type[BaseAction]:
        name = getattr(action_cls, "name", None)
        if not name:
            raise ValueError(f"Action class {action_cls.__name__} does not define name")
        if name in self._actions:
            raise ValueError(f"Action already registered: {name}")
        self._actions[name] = action_cls()
        return action_cls

    def get(self, name: str) -> BaseAction | None:
        return self._actions.get(name)

    def names(self) -> list[str]:
        return sorted(self._actions)


registry = ActionRegistry()
register_action = registry.register
