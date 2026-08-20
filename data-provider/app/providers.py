from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class DataProvider(ABC):
    name: str

    @abstractmethod
    def resolve(self, namespace: str, key: str, context: dict[str, Any]) -> dict[str, Any] | None:
        """Return a dataset or None when this backend has no matching data."""


class JsonFileProvider(DataProvider):
    name = "json-file"

    def __init__(self, path: Path):
        self.path = path

    def resolve(self, namespace: str, key: str, context: dict[str, Any]) -> dict[str, Any] | None:
        with self.path.open("r", encoding="utf-8") as handle:
            collection = json.load(handle).get(namespace, {})
        value = collection.get(key) if isinstance(collection, dict) else None
        return dict(value) if isinstance(value, dict) else None


class DataResolver:
    def __init__(self, providers: list[DataProvider]):
        self.providers = providers

    def resolve(self, namespace: str, key: str, context: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        for provider in self.providers:
            value = provider.resolve(namespace, key, context)
            if value is not None:
                return value, provider.name
        return None, None
