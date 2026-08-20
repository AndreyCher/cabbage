from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import json
import os
import pkgutil
import time
from pathlib import Path
from typing import Any

from .base import BasePlugin, PluginError


class HCaptchaChallengerPlugin(BasePlugin):
    """Experimental adapter for ``hcaptcha-challenger``.

    Upstream hcaptcha-challenger 0.19.x exposes an async Playwright/Camoufox
    AgentV API. Firefox worker currently owns a synchronous Playwright Page. To
    keep the same browser session/profile, this adapter bridges the sync Page's
    internal Playwright implementation to the async wrapper and executes the
    upstream coroutine through Playwright's own sync dispatcher via ``_sync``.

    This deliberately uses Playwright internals and therefore remains marked
    experimental until live-tested against the project's custom Camoufox build.
    """

    name = "hcaptcha-challenger"

    @staticmethod
    def _load_upstream():
        try:
            agent_mod = importlib.import_module("hcaptcha_challenger.agent")
            models_mod = importlib.import_module("hcaptcha_challenger.models")
            async_api = importlib.import_module("playwright.async_api")
            return agent_mod, models_mod, async_api
        except Exception as exc:
            raise PluginError(
                f"hcaptcha-challenger dependency is unavailable: {exc}",
                reason="plugin_dependency_missing",
                details={"dependency": "hcaptcha-challenger"},
            ) from exc

    @staticmethod
    def _async_page_from_sync(page, async_api):
        impl = getattr(page, "_impl_obj", None)
        sync_runner = getattr(page, "_sync", None)
        async_page_cls = getattr(async_api, "Page", None)
        if impl is None or not callable(sync_runner) or async_page_cls is None:
            raise PluginError(
                "Current Playwright Page cannot be bridged to hcaptcha-challenger async API",
                reason="hcaptcha_async_bridge_unavailable",
                details={"plugin": HCaptchaChallengerPlugin.name},
            )
        try:
            return async_page_cls(impl), sync_runner
        except Exception as exc:
            raise PluginError(
                f"Unable to create async Playwright Page bridge: {exc}",
                reason="hcaptcha_async_bridge_failed",
                details={"plugin": HCaptchaChallengerPlugin.name},
            ) from exc

    @staticmethod
    def _load_backend_symbol(adapter: str):
        if not adapter or ":" not in adapter:
            raise PluginError(
                "hCaptcha custom backend requires backend_adapter='module:Class'",
                reason="hcaptcha_backend_invalid_config",
                details={"plugin": HCaptchaChallengerPlugin.name},
            )
        module_name, symbol_name = adapter.split(":", 1)
        try:
            module = importlib.import_module(module_name)
            return getattr(module, symbol_name)
        except Exception as exc:
            raise PluginError(
                f"Unable to load hCaptcha backend '{adapter}': {exc}",
                reason="hcaptcha_backend_load_failed",
                details={"plugin": HCaptchaChallengerPlugin.name, "backend_adapter": adapter},
            ) from exc

    def _invoke_custom_backend(self, page, params: dict[str, Any]):
        adapter = params.get("backend_adapter") or self.config.get("backend_adapter")
        backend_cls = self._load_backend_symbol(str(adapter or ""))
        backend_config = dict(self.config.get("backend_config") or {})
        backend = backend_cls(backend_config)
        solve = getattr(backend, "solve", None)
        if not callable(solve):
            raise PluginError(
                f"hCaptcha backend '{adapter}' does not implement solve(page, params)",
                reason="hcaptcha_backend_api_incompatible",
                details={"plugin": self.name, "backend_adapter": adapter},
            )
        result = solve(page, params)
        if inspect.isawaitable(result):
            sync_runner = getattr(page, "_sync", None)
            if not callable(sync_runner):
                raise PluginError(
                    "Async hCaptcha backend cannot run because the sync Playwright dispatcher is unavailable",
                    reason="hcaptcha_async_bridge_unavailable",
                    details={"plugin": self.name, "backend_adapter": adapter},
                )
            result = sync_runner(result)
        if not isinstance(result, dict):
            result = {"success": bool(result), "response": result}
        result.setdefault("solver", str(adapter))
        result.setdefault("captcha_type", "hcaptcha")
        result.setdefault("backend", "custom")
        return result


    @staticmethod
    def _local_probe(ctx, page) -> dict[str, Any]:
        """Inspect the installed upstream package and the current page without Gemini.

        This is intentionally a user-facing diagnostic method rather than a claimed
        solver.  It lets live environments tell us which local/pluggable upstream
        resources are actually present before we bind the POC to unstable private APIs.
        """
        try:
            root = importlib.import_module("hcaptcha_challenger")
        except Exception as exc:
            raise PluginError(
                f"hcaptcha-challenger dependency is unavailable: {exc}",
                reason="plugin_dependency_missing",
                details={"dependency": "hcaptcha-challenger"},
            ) from exc

        try:
            version = importlib.metadata.version("hcaptcha-challenger")
        except Exception:
            version = getattr(root, "__version__", "unknown")

        package_paths = [str(Path(x).resolve()) for x in getattr(root, "__path__", [])]
        modules: list[str] = []
        for info in pkgutil.walk_packages(getattr(root, "__path__", []), prefix="hcaptcha_challenger."):
            name = info.name
            low = name.lower()
            if any(token in low for token in ("model", "onnx", "yolo", "resnet", "vit", "clip", "challenge", "solver", "agent")):
                modules.append(name)
        modules = sorted(set(modules))

        resource_files: list[str] = []
        for base in package_paths:
            root_path = Path(base)
            if not root_path.exists():
                continue
            for candidate in root_path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in {".onnx", ".pt", ".pth", ".yaml", ".yml"}:
                    try:
                        resource_files.append(str(candidate.relative_to(root_path)))
                    except Exception:
                        resource_files.append(str(candidate))
        resource_files = sorted(resource_files)[:200]

        frame_urls: list[str] = []
        try:
            frame_urls = [str(getattr(frame, "url", "")) for frame in getattr(page, "frames", [])]
        except Exception:
            pass
        hcaptcha_frame_urls = [url for url in frame_urls if "hcaptcha" in url.lower()]

        iframe_count = None
        response_count = None
        try:
            iframe_count = page.locator("iframe[src*='hcaptcha.com'], iframe[src*='hcaptcha']").count()
        except Exception:
            pass
        try:
            response_count = page.locator("textarea[name='h-captcha-response'], textarea[name='g-recaptcha-response']").count()
        except Exception:
            pass

        result = {
            "success": True,
            "plugin": HCaptchaChallengerPlugin.name,
            "probe": "local",
            "package_version": version,
            "package_paths": package_paths,
            "candidate_modules": modules,
            "local_resource_files": resource_files,
            "local_resource_file_count": len(resource_files),
            "hcaptcha_frame_count": len(hcaptcha_frame_urls),
            "hcaptcha_frame_urls": hcaptcha_frame_urls[:20],
            "hcaptcha_iframe_locator_count": iframe_count,
            "response_textarea_count": response_count,
            "gemini_api_key_present": bool(os.getenv("GEMINI_API_KEY")),
            "local_solver_ready": False,
            "note": "Probe only: local_probe does not claim a universal local hCaptcha solver.",
        }

        logger = getattr(ctx, "logger", None)
        if logger is not None:
            logger.info(
                "HCAPTCHA LOCAL probe version=%s modules=%d resources=%d frames=%d response_fields=%s",
                version, len(modules), len(resource_files), len(hcaptcha_frame_urls), response_count,
            )
            if modules:
                logger.info("HCAPTCHA LOCAL candidate modules: %s", ", ".join(modules[:20]))
            if resource_files:
                logger.info("HCAPTCHA LOCAL packaged resources: %s", ", ".join(resource_files[:20]))

        artifact_dir = getattr(ctx, "artifact_dir", None)
        if artifact_dir:
            try:
                out = Path(artifact_dir) / "hcaptcha-local-probe.json"
                out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result["artifact"] = str(out)
                if logger is not None:
                    logger.info("HCAPTCHA LOCAL probe saved: %s", out)
            except Exception as exc:
                if logger is not None:
                    logger.warning("HCAPTCHA LOCAL probe artifact write failed: %s", exc)
        return result


    @staticmethod
    def _checkbox_test(ctx, page, params: dict[str, Any]) -> dict[str, Any]:
        """Find and click the visible hCaptcha checkbox without invoking Gemini/AgentV.

        This is a user-facing interaction probe.  It uses the current Camoufox
        Playwright page and public frame APIs only.  A successful click may either
        open a visual challenge or immediately produce a response token.
        """
        timeout_ms = int(params.get("timeout_ms", 15000))
        post_click_wait_ms = int(params.get("post_click_wait_ms", 1500))
        logger = getattr(ctx, "logger", None)

        iframe_selectors = [
            "iframe[title*='hCaptcha'][title*='checkbox']",
            "iframe[title*='checkbox'][src*='hcaptcha']",
            "iframe[src*='hcaptcha.com']",
            "iframe[src*='hcaptcha']",
        ]
        checkbox_selectors = [
            "#checkbox",
            "[role='checkbox']",
            "input[type='checkbox']",
        ]

        before_frames = []
        try:
            before_frames = [str(getattr(frame, "url", "")) for frame in page.frames]
        except Exception:
            pass

        frame_used = None
        checkbox_used = None
        clicked = False
        last_error = None

        # Prefer Playwright's frame locator because it handles cross-origin frames.
        for iframe_selector in iframe_selectors:
            try:
                frame_locator = page.frame_locator(iframe_selector)
            except Exception as exc:
                last_error = exc
                continue
            for checkbox_selector in checkbox_selectors:
                try:
                    checkbox = frame_locator.locator(checkbox_selector)
                    checkbox.wait_for(state="visible", timeout=timeout_ms)
                    checkbox.click(timeout=timeout_ms)
                    frame_used = iframe_selector
                    checkbox_used = checkbox_selector
                    clicked = True
                    break
                except Exception as exc:
                    last_error = exc
            if clicked:
                break

        # Fallback to already attached Frame objects if frame_locator did not match.
        if not clicked:
            try:
                frames = list(page.frames)
            except Exception:
                frames = []
            for frame in frames:
                frame_url = str(getattr(frame, "url", ""))
                if "hcaptcha" not in frame_url.lower():
                    continue
                for checkbox_selector in checkbox_selectors:
                    try:
                        checkbox = frame.locator(checkbox_selector)
                        checkbox.wait_for(state="visible", timeout=timeout_ms)
                        checkbox.click(timeout=timeout_ms)
                        frame_used = frame_url
                        checkbox_used = checkbox_selector
                        clicked = True
                        break
                    except Exception as exc:
                        last_error = exc
                if clicked:
                    break

        if not clicked:
            raise PluginError(
                f"hCaptcha checkbox was not clickable: {last_error or 'checkbox not found'}",
                reason="hcaptcha_checkbox_not_found",
                details={"plugin": HCaptchaChallengerPlugin.name},
            )

        if logger is not None:
            logger.info("HCAPTCHA CHECKBOX clicked frame=%s selector=%s", frame_used, checkbox_used)

        if post_click_wait_ms > 0:
            try:
                page.wait_for_timeout(post_click_wait_ms)
            except Exception:
                time.sleep(post_click_wait_ms / 1000.0)

        response_value = ""
        response_field_count = 0
        try:
            response = page.locator("textarea[name='h-captcha-response']")
            response_field_count = response.count()
            for idx in range(response_field_count):
                try:
                    value = response.nth(idx).input_value(timeout=1000)
                except Exception:
                    try:
                        value = response.nth(idx).get_attribute("value") or ""
                    except Exception:
                        value = ""
                if value:
                    response_value = value
                    break
        except Exception:
            pass

        challenge_opened = False
        challenge_frame_urls: list[str] = []
        try:
            after_frames = [str(getattr(frame, "url", "")) for frame in page.frames]
            challenge_frame_urls = [
                url for url in after_frames
                if "hcaptcha" in url.lower() and ("challenge" in url.lower() or url not in before_frames)
            ]
            challenge_opened = bool(challenge_frame_urls)
        except Exception:
            pass

        try:
            challenge_locator_count = page.locator(
                "iframe[title*='challenge'][src*='hcaptcha'], iframe[src*='hcaptcha'][style*='visibility: visible']"
            ).count()
            challenge_opened = challenge_opened or challenge_locator_count > 0
        except Exception:
            challenge_locator_count = None

        result = {
            "success": True,
            "plugin": HCaptchaChallengerPlugin.name,
            "test": "checkbox",
            "checkbox_found": True,
            "checkbox_clicked": True,
            "frame": frame_used,
            "checkbox_selector": checkbox_used,
            "challenge_opened": challenge_opened,
            "challenge_frame_urls": challenge_frame_urls[:10],
            "challenge_iframe_locator_count": challenge_locator_count,
            "response_field_count": response_field_count,
            "response_present": bool(response_value),
            "response_length": len(response_value),
            "gemini_required": False,
            "note": "Interaction test only; visual challenge solving is not performed by checkbox_test.",
        }
        if logger is not None:
            logger.info(
                "HCAPTCHA CHECKBOX result clicked=%s challenge_opened=%s response_present=%s",
                clicked, challenge_opened, bool(response_value),
            )
        return result

    @staticmethod
    def _local_solve_test(ctx, page, params: dict[str, Any]) -> dict[str, Any]:
        """Attempt a non-Gemini hCaptcha solve path using only public/runtime resources.

        This method is intentionally conservative: it clicks the checkbox, inspects the
        live challenge and installed hcaptcha-challenger 0.19.x package, and only
        reports a local solver as ready if a stable end-to-end callable is actually
        discoverable without AgentV/Gemini.  It never silently falls back to Gemini.
        """
        logger = getattr(ctx, "logger", None)
        started = time.monotonic()
        checkbox = HCaptchaChallengerPlugin._checkbox_test(ctx, page, {
            "timeout_ms": int(params.get("timeout_ms", 15000)),
            "post_click_wait_ms": int(params.get("post_click_wait_ms", 1800)),
        })

        try:
            root = importlib.import_module("hcaptcha_challenger")
            version = importlib.metadata.version("hcaptcha-challenger")
        except Exception as exc:
            raise PluginError(
                f"hcaptcha-challenger dependency is unavailable: {exc}",
                reason="plugin_dependency_missing",
                details={"dependency": "hcaptcha-challenger"},
            ) from exc

        candidates = []
        # Public-ish historical/local names that can be inspected safely. We do not
        # instantiate unknown classes because doing so may invoke remote AI implicitly.
        probes = [
            ("hcaptcha_challenger", ["Challenger", "Solver", "LocalSolver"]),
            ("hcaptcha_challenger.agent", ["AgentT", "AgentQ", "LocalAgent", "Solver"]),
            ("hcaptcha_challenger.cli.solver", ["Solver", "solve", "run"]),
            ("hcaptcha_challenger.tools", ["Solver", "solve"]),
        ]
        for module_name, symbols in probes:
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                candidates.append({"module": module_name, "importable": False, "error": str(exc)})
                continue
            found = []
            for symbol in symbols:
                obj = getattr(module, symbol, None)
                if obj is not None:
                    found.append({
                        "name": symbol,
                        "callable": callable(obj),
                        "kind": type(obj).__name__,
                    })
            candidates.append({"module": module_name, "importable": True, "symbols": found})

        # Inspect packaged local model files. v0.19.0 normally ships rules but not the
        # model zoo itself; this distinction is important for deciding whether a true
        # offline solver is immediately usable.
        model_files = []
        for base in getattr(root, "__path__", []):
            rp = Path(base)
            if not rp.exists():
                continue
            for item in rp.rglob("*"):
                if item.is_file() and item.suffix.lower() in {".onnx", ".pt", ".pth", ".engine", ".tflite"}:
                    try:
                        model_files.append(str(item.relative_to(rp)))
                    except Exception:
                        model_files.append(str(item))
        model_files = sorted(model_files)[:200]

        challenge_frames = []
        try:
            for frame in page.frames:
                url = str(getattr(frame, "url", ""))
                if "hcaptcha" in url.lower():
                    challenge_frames.append(url)
        except Exception:
            pass

        result = {
            "success": False,
            "plugin": HCaptchaChallengerPlugin.name,
            "test": "local_solve",
            "package_version": version,
            "gemini_used": False,
            "gemini_api_key_present": bool(os.getenv("GEMINI_API_KEY")),
            "checkbox": checkbox,
            "challenge_frames": challenge_frames[:20],
            "local_entrypoint_candidates": candidates,
            "packaged_model_files": model_files,
            "packaged_model_file_count": len(model_files),
            "local_solver_ready": False,
            "decision": "no_stable_non_gemini_end_to_end_solver_discovered",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "note": (
                "hcaptcha-challenger 0.19.x exposes local model concepts, but this runtime "
                "did not expose a stable configuration-only end-to-end local solver. No Gemini fallback was used."
            ),
        }

        artifact_dir = getattr(ctx, "artifact_dir", None)
        if artifact_dir:
            try:
                out = Path(artifact_dir) / "hcaptcha-local-solve-test.json"
                out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result["artifact"] = str(out)
            except Exception as exc:
                if logger is not None:
                    logger.warning("HCAPTCHA LOCAL SOLVE artifact write failed: %s", exc)

        if logger is not None:
            logger.info(
                "HCAPTCHA LOCAL SOLVE test version=%s checkbox_clicked=%s challenge_opened=%s models=%d",
                version, checkbox.get("checkbox_clicked"), checkbox.get("challenge_opened"), len(model_files),
            )
            logger.warning(
                "HCAPTCHA LOCAL SOLVE unavailable: no stable non-Gemini end-to-end solver discovered in hcaptcha-challenger %s",
                version,
            )

        raise PluginError(
            "No stable non-Gemini end-to-end local solver is available in the installed hcaptcha-challenger runtime",
            reason="hcaptcha_local_solver_unavailable",
            details={
                "plugin": HCaptchaChallengerPlugin.name,
                "package_version": version,
                "artifact": result.get("artifact"),
                "gemini_used": False,
            },
        )

    def invoke(self, method: str, ctx, params: dict[str, Any]) -> Any:
        if method == "capabilities":
            return {
                "success": True,
                "plugin": self.name,
                "backends": ["agentv", "custom"],
                "diagnostics": ["local_probe", "checkbox_test", "local_solve_test"],
                "agentv_requires_gemini": True,
                "custom_backend_contract": "Class(config).solve(page, params)",
                "upstream_local_resources": ["ResNet ONNX", "YOLOv8 ONNX", "ViT ONNX"],
                "built_in_local_solver": False,
            }
        if method == "local_probe":
            page = ctx.ensure_page()
            return self._local_probe(ctx, page)
        if method == "checkbox_test":
            page = ctx.ensure_page()
            return self._checkbox_test(ctx, page, params)
        if method == "local_solve_test":
            page = ctx.ensure_page()
            return self._local_solve_test(ctx, page, params)
        if method not in {"solve", "solve_checkbox"}:
            raise PluginError(
                f"Unsupported hcaptcha-challenger method: {method}",
                reason="plugin_method_not_supported",
                details={"plugin": self.name, "method": method},
            )

        page = ctx.ensure_page()
        backend = str(params.get("backend", self.config.get("backend", "agentv"))).lower()
        if backend == "custom":
            started = time.monotonic()
            result = self._invoke_custom_backend(page, params)
            result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            return result
        if backend != "agentv":
            raise PluginError(
                f"Unsupported hCaptcha backend: {backend}",
                reason="hcaptcha_backend_not_supported",
                details={"plugin": self.name, "backend": backend},
            )

        agent_mod, _models_mod, async_api = self._load_upstream()
        AgentV = getattr(agent_mod, "AgentV", None)
        AgentConfig = getattr(agent_mod, "AgentConfig", None)
        if AgentV is None or AgentConfig is None:
            raise PluginError(
                "hcaptcha-challenger AgentV/AgentConfig API is unavailable",
                reason="hcaptcha_api_incompatible",
                details={"plugin": self.name},
            )

        async_page, sync_runner = self._async_page_from_sync(page, async_api)
        click_checkbox = bool(params.get("click_checkbox", self.config.get("click_checkbox", True)))
        disable_bezier = bool(
            params.get(
                "disable_bezier_trajectory",
                self.config.get("disable_bezier_trajectory", True),
            )
        )
        enable_debug = bool(params.get("debug", self.config.get("debug", False)))

        async def _solve():
            kwargs: dict[str, Any] = {"DISABLE_BEZIER_TRAJECTORY": disable_bezier}
            # Introduced by recent upstream versions; only pass when the model
            # accepts it so older compatible 0.17+ builds remain usable.
            if enable_debug:
                kwargs["enable_challenger_debug"] = True
            try:
                agent_config = AgentConfig(**kwargs)
            except TypeError:
                kwargs.pop("enable_challenger_debug", None)
                agent_config = AgentConfig(**kwargs)

            agent = AgentV(page=async_page, agent_config=agent_config)
            if click_checkbox:
                await agent.robotic_arm.click_checkbox()
            await agent.wait_for_challenge()

            responses = getattr(agent, "cr_list", None) or []
            last_response = responses[-1] if responses else None
            if last_response is None:
                return {
                    "success": True,
                    "captcha_type": "hcaptcha",
                    "solver": "hcaptcha-challenger",
                    "response": None,
                }

            if hasattr(last_response, "model_dump"):
                try:
                    payload = last_response.model_dump(by_alias=True)
                except TypeError:
                    payload = last_response.model_dump()
            else:
                payload = str(last_response)
            return {
                "success": True,
                "captcha_type": "hcaptcha",
                "solver": "hcaptcha-challenger",
                "response": payload,
            }

        started = time.monotonic()
        try:
            result = sync_runner(_solve())
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                f"hCaptcha solve failed: {exc}",
                reason="hcaptcha_solve_failed",
                details={"plugin": self.name, "method": method},
            ) from exc

        if not isinstance(result, dict):
            result = {"success": True, "response": result}
        result.setdefault("captcha_type", "hcaptcha")
        result.setdefault("solver", "hcaptcha-challenger")
        result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        result["experimental_async_bridge"] = True
        result["backend"] = "agentv"
        return result
