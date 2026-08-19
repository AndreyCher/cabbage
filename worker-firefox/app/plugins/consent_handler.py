from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .base import BasePlugin, PluginError


class ConsentHandlerPlugin(BasePlugin):
    """Cookie/CMP consent handler with provider-specific and generic fallbacks."""

    name = "consent-handler"

    PROVIDERS = {
        "onetrust": {
            "accept_all": [
                "#onetrust-accept-btn-handler",
            ],
            "reject_optional": [
                "#onetrust-reject-all-handler",
            ],
        },
        "cookiebot": {
            "accept_all": [
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                "#CybotCookiebotDialogBodyButtonAccept",
            ],
            "reject_optional": [
                "#CybotCookiebotDialogBodyButtonDecline",
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinDeclineAll",
            ],
        },
        "didomi": {
            "accept_all": [
                "#didomi-notice-agree-button",
                "button#didomi-notice-agree-button",
            ],
            "reject_optional": [
                "#didomi-notice-disagree-button",
            ],
        },
        "cookieyes": {
            "accept_all": [
                ".cky-btn-accept",
                "button.cky-btn-accept",
            ],
            "reject_optional": [
                ".cky-btn-reject",
                "button.cky-btn-reject",
            ],
        },
        "iubenda": {
            "accept_all": [
                ".iubenda-cs-accept-btn",
                "button.iubenda-cs-accept-btn",
            ],
            "reject_optional": [
                ".iubenda-cs-reject-btn",
                "button.iubenda-cs-reject-btn",
            ],
        },
        "quantcast": {
            "accept_all": [
                ".qc-cmp2-summary-buttons button[mode='primary']",
                "button[mode='primary']",
            ],
            "reject_optional": [
                ".qc-cmp2-summary-buttons button[mode='secondary']",
            ],
        },
        "trustarc": {
            "accept_all": [
                ".trustarc-agree-btn",
                "#truste-consent-button",
            ],
            "reject_optional": [
                ".trustarc-decline-btn",
            ],
        },
    }

    DEFAULT_ACCEPT_TEXTS = [
        "accept all", "accept cookies", "allow all", "agree", "i agree",
        "прийняти всі", "прийняти", "дозволити всі", "погоджуюсь",
        "alle akzeptieren", "akzeptieren", "alle zulassen", "zustimmen",
        "tout accepter", "accepter", "accepter tout",
        "aceptar todo", "aceptar", "permitir todo",
        "accetta tutto", "accetta", "consenti tutto",
        "akceptuj wszystkie", "zaakceptuj wszystkie", "akceptuj",
    ]

    DEFAULT_REJECT_TEXTS = [
        "reject all", "reject optional", "decline", "deny", "necessary only",
        "відхилити всі", "відхилити", "лише необхідні",
        "alle ablehnen", "ablehnen", "nur notwendige",
        "tout refuser", "refuser",
        "rechazar todo", "rechazar",
        "rifiuta tutto", "rifiuta",
        "odrzuć wszystkie", "odrzuć",
    ]

    def invoke(self, method: str, ctx, params: dict[str, Any]) -> Any:
        if method == "handle":
            return self._handle(ctx, params)
        if method == "detect":
            return self._detect(ctx, params)
        raise PluginError(
            f"Unsupported consent-handler method: {method}",
            reason="plugin_method_not_supported",
            details={"plugin": self.name, "method": method},
        )

    @staticmethod
    def _scopes(page):
        # Main page first, then every attached frame. Playwright frame objects
        # expose locator/get_by_role directly, including cross-origin frames.
        scopes = [("main", page)]
        for idx, frame in enumerate(getattr(page, "frames", []) or []):
            if frame is page.main_frame:
                continue
            scopes.append((f"frame:{idx}:{getattr(frame, 'url', '')}", frame))
        return scopes

    @staticmethod
    def _visible(locator) -> bool:
        try:
            return locator.is_visible(timeout=250)
        except Exception:
            try:
                return locator.is_visible()
            except Exception:
                return False

    @staticmethod
    def _first_visible(scope, selectors):
        for selector in selectors:
            try:
                locator = scope.locator(selector).first
                if ConsentHandlerPlugin._visible(locator):
                    return locator, selector
            except Exception:
                continue
        return None, None

    def _provider_selectors(self, policy: str):
        custom = self.config.get("providers", {})
        providers = dict(self.PROVIDERS)
        if isinstance(custom, dict):
            for name, cfg in custom.items():
                if not isinstance(cfg, dict):
                    continue
                base = dict(providers.get(name, {}))
                for key in ("accept_all", "reject_optional"):
                    if isinstance(cfg.get(key), list):
                        base[key] = [str(v) for v in cfg[key]]
                providers[str(name)] = base
        for provider, cfg in providers.items():
            yield provider, list(cfg.get(policy, []))

    def _text_pattern(self, policy: str, params: dict[str, Any]):
        key = "accept_texts" if policy == "accept_all" else "reject_texts"
        defaults = self.DEFAULT_ACCEPT_TEXTS if policy == "accept_all" else self.DEFAULT_REJECT_TEXTS
        texts = params.get(key, self.config.get(key, defaults))
        if not isinstance(texts, list) or not texts:
            texts = defaults
        # exact-ish button-name matching; whitespace is normalized by Playwright.
        alternatives = "|".join(re.escape(str(v).strip()) for v in texts if str(v).strip())
        return re.compile(rf"^\s*(?:{alternatives})\s*$", re.IGNORECASE)

    def _detect(self, ctx, params):
        page = ctx.ensure_page()
        detected = []
        for scope_name, scope in self._scopes(page):
            for provider, selectors in self._provider_selectors("accept_all"):
                locator, selector = self._first_visible(scope, selectors)
                if locator is not None:
                    detected.append({
                        "provider": provider,
                        "scope": scope_name,
                        "selector": selector,
                    })
        result = {
            "success": True,
            "detected": bool(detected),
            "matches": detected,
        }
        self._save_artifact(ctx, "consent-detect.json", result)
        return result

    def _handle(self, ctx, params):
        policy = str(params.get("policy", self.config.get("policy", "accept_all"))).lower()
        if policy not in {"accept_all", "reject_optional"}:
            raise PluginError(
                f"Unsupported consent policy: {policy}",
                reason="consent_invalid_policy",
                details={"policy": policy},
            )

        page = ctx.ensure_page()
        timeout_ms = int(params.get("timeout_ms", self.config.get("timeout_ms", 10000)))
        required = bool(params.get("required", self.config.get("required", False)))
        generic_fallback = bool(params.get("generic_fallback", self.config.get("generic_fallback", True)))
        if timeout_ms <= 0:
            raise PluginError(
                "consent-handler timeout_ms must be greater than 0",
                reason="plugin_invalid_config",
            )

        # Wait in short Playwright-aware slices so banners injected after load
        # can appear while keeping the action responsive.
        deadline = __import__("time").monotonic() + timeout_ms / 1000.0
        attempts = 0
        while True:
            attempts += 1
            for scope_name, scope in self._scopes(page):
                for provider, selectors in self._provider_selectors(policy):
                    locator, selector = self._first_visible(scope, selectors)
                    if locator is None:
                        continue
                    locator.click(timeout=max(1000, min(5000, timeout_ms)))
                    result = {
                        "success": True,
                        "handled": True,
                        "policy": policy,
                        "provider": provider,
                        "strategy": "provider_selector",
                        "scope": scope_name,
                        "selector": selector,
                        "attempts": attempts,
                    }
                    ctx.logger.info(
                        "CONSENT handled policy=%s provider=%s scope=%s selector=%s",
                        policy, provider, scope_name, selector,
                    )
                    self._save_artifact(ctx, "consent-handler.json", result)
                    return result

                if generic_fallback:
                    pattern = self._text_pattern(policy, params)
                    # Prefer semantic role=button; fall back to link-like controls.
                    candidates = []
                    try:
                        candidates.append(("role=button", scope.get_by_role("button", name=pattern).first))
                    except Exception:
                        pass
                    try:
                        candidates.append((
                            "generic-control-text",
                            scope.locator('button, [role="button"], input[type="button"], input[type="submit"], a')
                                 .filter(has_text=pattern).first,
                        ))
                    except Exception:
                        pass
                    for strategy, locator in candidates:
                        if self._visible(locator):
                            locator.click(timeout=max(1000, min(5000, timeout_ms)))
                            result = {
                                "success": True,
                                "handled": True,
                                "policy": policy,
                                "provider": "generic",
                                "strategy": strategy,
                                "scope": scope_name,
                                "matched_text_pattern": pattern.pattern,
                                "attempts": attempts,
                            }
                            ctx.logger.info(
                                "CONSENT handled policy=%s provider=generic scope=%s strategy=%s",
                                policy, scope_name, strategy,
                            )
                            self._save_artifact(ctx, "consent-handler.json", result)
                            return result

            if __import__("time").monotonic() >= deadline:
                break
            page.wait_for_timeout(min(250, max(1, int((deadline - __import__("time").monotonic()) * 1000))))

        result = {
            "success": not required,
            "handled": False,
            "policy": policy,
            "provider": None,
            "strategy": None,
            "reason": "consent_not_found",
            "attempts": attempts,
        }
        self._save_artifact(ctx, "consent-handler.json", result)
        if required:
            raise PluginError(
                f"No matching consent control found within {timeout_ms} ms",
                reason="consent_not_found",
                details={"policy": policy, "timeout_ms": timeout_ms},
            )
        ctx.logger.info("CONSENT not found policy=%s; continuing because required=false", policy)
        return result

    @staticmethod
    def _save_artifact(ctx, name: str, payload: dict[str, Any]) -> None:
        try:
            path = Path(ctx.artifact_dir) / name
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            try:
                ctx.logger.warning("CONSENT artifact write failed: %s", exc)
            except Exception:
                pass
