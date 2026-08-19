from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .context import ScenarioContext


class BaseAction(ABC):
    """Contract implemented by every scenario action module."""

    name: str

    @abstractmethod
    def execute(self, ctx: ScenarioContext, action: dict[str, Any], index: int) -> dict[str, Any]:
        raise NotImplementedError
