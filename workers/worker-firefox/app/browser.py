from __future__ import annotations

import os
from typing import Any

from camoufox.sync_api import Camoufox

from .proxy import validate_proxy_config


def uses_x11_recording(cfg: dict[str, Any]) -> bool:
    recording = cfg.get("recording", {})
    if not recording.get("video", False):
        return False
    mode = cfg.get("browser", {}).get("mode", "virtual")
    backend_key = "debug_backend" if mode == "debug" else "backend"
    return recording.get(backend_key, "x11") == "x11"


def _proxy_config(cfg: dict[str, Any]) -> dict[str, str] | None:
    proxy = validate_proxy_config(cfg)
    if proxy is None:
        return None
    server = proxy.get("server")
    result: dict[str, str] = {"server": server}
    if proxy.get("username"):
        result["username"] = proxy["username"]
    if proxy.get("password"):
        result["password"] = proxy["password"]
    if proxy.get("bypass"):
        result["bypass"] = proxy["bypass"]
    return result




def _locale_from_camou_config(camou_config: dict[str, Any]) -> str | list[str] | None:
    """Reconstruct Camoufox's public locale= value from persisted Identity config."""
    language = camou_config.get("locale:language")
    region = camou_config.get("locale:region")
    primary = f"{language}-{region}" if language and region else (str(language) if language else None)

    raw_all = camou_config.get("locale:all")
    accepted: list[str] = []
    if isinstance(raw_all, str):
        accepted = [part.strip() for part in raw_all.split(",") if part.strip()]
    elif isinstance(raw_all, list):
        accepted = [str(part).strip() for part in raw_all if str(part).strip()]

    locales: list[str] = []
    if primary:
        locales.append(primary)
    for value in accepted:
        if value not in locales:
            locales.append(value)

    if not locales:
        return None
    return locales[0] if len(locales) == 1 else locales


def _config_without_locale_keys(camou_config: dict[str, Any]) -> dict[str, Any]:
    """Keep persistent fingerprint config but let Camoufox own locale:* injection."""
    result = dict(camou_config)
    for key in ("locale:language", "locale:region", "locale:script", "locale:all"):
        result.pop(key, None)
    return result

def build_camoufox_kwargs(cfg: dict[str, Any], identity_state: dict[str, Any], run_dir: str | None = None) -> dict[str, Any]:
    browser_cfg = cfg.get("browser", {})
    proxy = _proxy_config(cfg)

    mode = browser_cfg.get("mode", "virtual")
    x11_recording = uses_x11_recording(cfg)
    if mode == "debug" or x11_recording:
        headless: bool | str = False
        if not os.getenv("DISPLAY"):
            raise RuntimeError("X11 browser mode requires DISPLAY")
    elif mode == "headless":
        headless = True
    else:
        headless = "virtual"

    launch_config = dict(identity_state.get("launch_camou_config", identity_state["camou_config"]))
    persisted_locale = _locale_from_camou_config(launch_config)

    kwargs: dict[str, Any] = {
        "headless": headless,
        "humanize": browser_cfg.get("humanize", 1.8),
        "enable_cache": browser_cfg.get("enable_cache", True),
        "persistent_context": True,
        "user_data_dir": str(identity_state["paths"]["profile"]),
        "browser": browser_cfg.get("version", "152.0.4-beta.28"),
        # Locale is deliberately removed from low-level config and supplied
        # through Camoufox's public locale= API.  Timezone/geolocation remain
        # persisted config because they are Identity-owned at normal runtime.
        "config": _config_without_locale_keys(launch_config),
        "i_know_what_im_doing": True,
    }
    if persisted_locale is not None:
        kwargs["locale"] = persisted_locale

    resolved_window = identity_state.get("resolved_window")
    if resolved_window:
        kwargs["window"] = (int(resolved_window["width"]), int(resolved_window["height"]))

    custom_executable = os.getenv("CAMOUFOX_EXECUTABLE_PATH")
    if custom_executable:
        if not os.path.isfile(custom_executable):
            raise RuntimeError(f"CAMOUFOX_EXECUTABLE_PATH does not exist: {custom_executable}")
        kwargs["executable_path"] = custom_executable
        # A custom executable wins over the package-manager browser selector.
        kwargs.pop("browser", None)

    recording = cfg.get("recording", {})
    if recording.get("video", False) and not x11_recording:
        if not run_dir:
            raise ValueError("run_dir is required when recording.video=true")
        kwargs["record_video_dir"] = f"{run_dir}/videos/.raw"
        video_size = recording.get("video_size", "default")
        if video_size == "default":
            # QA-friendly default: readable text without forcing every config to specify a size.
            kwargs["record_video_size"] = {"width": 1600, "height": 900}
        elif video_size == "playwright-default":
            # Native Playwright behavior: do not pass record_video_size.
            pass
        else:
            if not isinstance(video_size, dict) or "width" not in video_size or "height" not in video_size:
                raise ValueError(
                    "recording.video_size must be 'default', 'playwright-default', or {width,height}"
                )
            width = int(video_size["width"])
            height = int(video_size["height"])
            if width <= 0 or height <= 0:
                raise ValueError("recording.video_size width/height must be positive integers")
            kwargs["record_video_size"] = {"width": width, "height": height}

    if proxy:
        kwargs["proxy"] = proxy
        # v0.4.33: never pass geoip during a normal browser launch.
        # locale/timezone/languages/geolocation are persisted in the Identity
        # camoufox_config and must not drift when the proxy changes.

    return kwargs


def launch(cfg: dict[str, Any], identity_state: dict[str, Any], run_dir: str | None = None) -> Camoufox:
    return Camoufox(**build_camoufox_kwargs(cfg, identity_state, run_dir=run_dir))
