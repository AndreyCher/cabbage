from __future__ import annotations

import importlib
import os
import warnings
import time
from typing import Any

from .base import BasePlugin, PluginError


class PlaywrightRecaptchaPlugin(BasePlugin):
    """Adapter for the third-party ``playwright-recaptcha`` package.

    v0.5.2 intentionally exposes reCAPTCHA v2 first. The upstream v3 solver
    must be initialized before navigation so it can install its network
    listener; that needs a prepare-before-open lifecycle and remains roadmap
    work rather than being hidden behind a fragile implementation.
    """

    name = "playwright-recaptcha"

    @staticmethod
    def _load_v2_module():
        try:
            # pydub 0.25.1 emits Python 3.12 SyntaxWarning messages while its
            # regex helpers are imported. These warnings are upstream source
            # noise, not runtime failures. Suppress only pydub SyntaxWarning.
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    category=SyntaxWarning,
                    module=r"pydub(?:\..*)?$",
                )
                return importlib.import_module("playwright_recaptcha.recaptchav2")
        except Exception as exc:
            raise PluginError(
                f"playwright-recaptcha dependency is unavailable: {exc}",
                reason="plugin_dependency_missing",
                details={"dependency": "playwright-recaptcha"},
            ) from exc

    def invoke(self, method: str, ctx, params: dict[str, Any]) -> Any:
        if method != "solve_v2":
            raise PluginError(
                f"Unsupported playwright-recaptcha method: {method}",
                reason="plugin_method_not_supported",
                details={"plugin": self.name, "method": method},
            )

        page = ctx.ensure_page()
        wait = bool(params.get("wait", self.config.get("default_wait", True)))
        image_challenge = bool(
            params.get("image_challenge", self.config.get("image_challenge", False))
        )

        # CapSolver is optional and is only needed when image_challenge=true.
        # Keep secrets out of logs/results. Prefer an environment variable, then
        # the isolated plugin config for deployments that explicitly choose it.
        capsolver_api_key = os.getenv("CAPSOLVER_API_KEY") or self.config.get("capsolver_api_key")
        if image_challenge and not capsolver_api_key:
            raise PluginError(
                "image_challenge=true requires CAPSOLVER_API_KEY or plugins.items.<name>.config.capsolver_api_key",
                reason="plugin_invalid_config",
                details={"plugin": self.name, "method": method},
            )

        recaptchav2 = self._load_v2_module()
        solver_kwargs: dict[str, Any] = {}
        if capsolver_api_key:
            solver_kwargs["capsolver_api_key"] = str(capsolver_api_key)

        started = time.monotonic()
        try:
            with recaptchav2.SyncSolver(page, **solver_kwargs) as solver:
                token = solver.solve_recaptcha(wait=wait, image_challenge=image_challenge)
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                f"reCAPTCHA v2 solve failed: {exc}",
                reason="recaptcha_v2_solve_failed",
                details={"plugin": self.name, "method": method},
            ) from exc

        if not token:
            raise PluginError(
                "reCAPTCHA v2 solver returned an empty token",
                reason="recaptcha_v2_empty_token",
                details={"plugin": self.name, "method": method},
            )

        return {
            "success": True,
            "captcha_type": "recaptcha_v2",
            "solver": "playwright-recaptcha",
            "mode": "image" if image_challenge else "audio",
            "wait": wait,
            "token": str(token),
            "token_length": len(str(token)),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
