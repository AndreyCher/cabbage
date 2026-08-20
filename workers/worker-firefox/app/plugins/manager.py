from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from .base import BasePlugin, PluginError


@dataclass(frozen=True)
class PluginSpec:
    name: str
    adapter: str
    enabled: bool
    config: dict[str, Any]


def _load_symbol(path: str):
    if ":" not in path:
        raise PluginError(
            f"Plugin adapter must use 'module:Class' syntax: {path!r}",
            reason="plugin_invalid_adapter",
            details={"adapter": path},
        )
    module_name, symbol_name = path.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise PluginError(
            f"Unable to import plugin module {module_name!r}: {exc}",
            reason="plugin_import_failed",
            details={"adapter": path},
        ) from exc
    try:
        return getattr(module, symbol_name)
    except AttributeError as exc:
        raise PluginError(
            f"Plugin adapter class {symbol_name!r} not found in {module_name!r}",
            reason="plugin_import_failed",
            details={"adapter": path},
        ) from exc


class PluginManager:
    """Loads enabled plugin adapters lazily and owns their per-run lifecycle."""

    def __init__(self, cfg: dict[str, Any] | None, logger=None):
        self.logger = logger
        self.specs = self._parse_specs(cfg or {})
        self.instances: dict[str, BasePlugin] = {}
        self._setup_done: set[str] = set()

    @staticmethod
    def _parse_specs(cfg: dict[str, Any]) -> dict[str, PluginSpec]:
        plugins_cfg = cfg.get("plugins", {})
        if plugins_cfg is None:
            return {}
        if not isinstance(plugins_cfg, dict):
            raise PluginError("'plugins' must be an object", reason="plugin_invalid_config")

        globally_enabled = bool(plugins_cfg.get("enabled", True))
        raw_items = plugins_cfg.get("items", {})
        if raw_items is None:
            raw_items = {}
        if not isinstance(raw_items, dict):
            raise PluginError("'plugins.items' must be an object", reason="plugin_invalid_config")

        specs: dict[str, PluginSpec] = {}
        for name, raw in raw_items.items():
            if not isinstance(raw, dict):
                raise PluginError(
                    f"Plugin {name!r} configuration must be an object",
                    reason="plugin_invalid_config",
                    details={"plugin": name},
                )
            adapter = str(raw.get("adapter", "")).strip()
            enabled = globally_enabled and bool(raw.get("enabled", False))
            if enabled and not adapter:
                raise PluginError(
                    f"Enabled plugin {name!r} requires 'adapter'",
                    reason="plugin_invalid_config",
                    details={"plugin": name},
                )
            plugin_cfg = raw.get("config", {})
            if plugin_cfg is None:
                plugin_cfg = {}
            if not isinstance(plugin_cfg, dict):
                raise PluginError(
                    f"Plugin {name!r} 'config' must be an object",
                    reason="plugin_invalid_config",
                    details={"plugin": name},
                )
            specs[str(name)] = PluginSpec(
                name=str(name),
                adapter=adapter,
                enabled=enabled,
                config=plugin_cfg,
            )
        return specs

    def enabled_names(self) -> list[str]:
        return sorted(name for name, spec in self.specs.items() if spec.enabled)

    def get(self, name: str, ctx) -> BasePlugin:
        spec = self.specs.get(name)
        if spec is None:
            raise PluginError(
                f"Unknown plugin: {name}",
                reason="plugin_not_configured",
                details={"plugin": name},
            )
        if not spec.enabled:
            raise PluginError(
                f"Plugin is disabled: {name}",
                reason="plugin_disabled",
                details={"plugin": name},
            )

        instance = self.instances.get(name)
        if instance is None:
            cls = _load_symbol(spec.adapter)
            if not isinstance(cls, type) or not issubclass(cls, BasePlugin):
                raise PluginError(
                    f"Adapter {spec.adapter!r} must inherit BasePlugin",
                    reason="plugin_invalid_adapter",
                    details={"plugin": name, "adapter": spec.adapter},
                )
            try:
                instance = cls(spec.config)
            except Exception as exc:
                raise PluginError(
                    f"Plugin {name!r} initialization failed: {exc}",
                    reason="plugin_init_failed",
                    details={"plugin": name, "adapter": spec.adapter},
                ) from exc
            self.instances[name] = instance

        if name not in self._setup_done:
            try:
                instance.setup(ctx)
            except PluginError:
                raise
            except Exception as exc:
                raise PluginError(
                    f"Plugin {name!r} setup failed: {exc}",
                    reason="plugin_setup_failed",
                    details={"plugin": name},
                ) from exc
            self._setup_done.add(name)
            if self.logger:
                self.logger.info("PLUGIN %-20s setup", name)
        return instance

    def invoke(self, name: str, method: str, ctx, params: dict[str, Any] | None = None) -> Any:
        plugin = self.get(name, ctx)
        if not method:
            raise PluginError(
                f"Plugin {name!r} call requires method",
                reason="plugin_invalid_call",
                details={"plugin": name},
            )
        try:
            result = plugin.invoke(method, ctx, dict(params or {}))
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                f"Plugin {name!r} method {method!r} failed: {exc}",
                reason="plugin_invoke_failed",
                details={"plugin": name, "method": method},
            ) from exc
        return {} if result is None else result

    def teardown_all(self, ctx) -> None:
        for name in reversed(list(self.instances.keys())):
            instance = self.instances[name]
            if name not in self._setup_done:
                continue
            try:
                instance.teardown(ctx)
                if self.logger:
                    self.logger.info("PLUGIN %-20s teardown", name)
            except Exception as exc:
                if self.logger:
                    self.logger.warning("PLUGIN %-20s teardown failed: %s", name, exc)
