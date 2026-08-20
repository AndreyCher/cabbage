from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILE_CONFIG_SCHEMA_VERSION = 1
DEFAULT = "default"

PROFILE_FINGERPRINT_KEYS = {
    "os",
    "preset",
    "screen",
    "locale",
    "languages",
    "timezone",
    "window",
    "device_pixel_ratio",
    "hardware_concurrency",
    "webgl",
}
GENERATION_KEYS = {"os", "preset", "screen", "locale", "languages", "timezone"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_default(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.lower() == DEFAULT)


def default_profile_config(identity: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": PROFILE_CONFIG_SCHEMA_VERSION,
        "identity": identity,
        "created_at": now,
        "updated_at": now,
        "baseline_stale": False,
        "fingerprint": {
            "os": DEFAULT,
            "preset": DEFAULT,
            "screen": DEFAULT,
            "locale": DEFAULT,
            "languages": DEFAULT,
            "timezone": DEFAULT,
            "window": DEFAULT,
            "device_pixel_ratio": DEFAULT,
            "hardware_concurrency": DEFAULT,
            "webgl": DEFAULT,
        },
    }


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_profile_config(data: dict[str, Any], *, identity: str | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Identity profile config must be a JSON object")
    fp = data.get("fingerprint", {})
    if not isinstance(fp, dict):
        raise ValueError("fingerprint must be an object")
    unknown = set(fp) - PROFILE_FINGERPRINT_KEYS
    if unknown:
        raise ValueError(f"Unknown profile fingerprint keys: {', '.join(sorted(unknown))}")

    result = copy.deepcopy(data)
    if identity is not None:
        result["identity"] = identity
    result["schema_version"] = PROFILE_CONFIG_SCHEMA_VERSION
    result["baseline_stale"] = bool(result.get("baseline_stale", False))
    result.setdefault("fingerprint", {})
    for key in PROFILE_FINGERPRINT_KEYS:
        result["fingerprint"].setdefault(key, DEFAULT)

    win = result["fingerprint"].get("window")
    if not is_default(win):
        if not isinstance(win, dict) or set(win) != {"width", "height"}:
            raise ValueError("fingerprint.window must be 'default' or {width,height}")
        if int(win["width"]) <= 0 or int(win["height"]) <= 0:
            raise ValueError("fingerprint.window width/height must be positive")
        win["width"], win["height"] = int(win["width"]), int(win["height"])

    dpr = result["fingerprint"].get("device_pixel_ratio")
    if not is_default(dpr):
        dpr = float(dpr)
        if dpr <= 0:
            raise ValueError("fingerprint.device_pixel_ratio must be positive")
        result["fingerprint"]["device_pixel_ratio"] = dpr

    hc = result["fingerprint"].get("hardware_concurrency")
    if not is_default(hc):
        hc = int(hc)
        if hc <= 0:
            raise ValueError("fingerprint.hardware_concurrency must be positive")
        result["fingerprint"]["hardware_concurrency"] = hc

    webgl = result["fingerprint"].get("webgl")
    if not is_default(webgl):
        if not isinstance(webgl, dict) or set(webgl) != {"vendor", "renderer"}:
            raise ValueError("fingerprint.webgl must be 'default' or {vendor,renderer}")
        if not str(webgl["vendor"]).strip() or not str(webgl["renderer"]).strip():
            raise ValueError("fingerprint.webgl vendor/renderer cannot be empty")
        webgl["vendor"], webgl["renderer"] = str(webgl["vendor"]), str(webgl["renderer"])

    preset = result["fingerprint"].get("preset")
    if not is_default(preset) and not isinstance(preset, bool):
        raise ValueError("fingerprint.preset must be 'default', true or false")

    locale = result["fingerprint"].get("locale")
    if not is_default(locale) and not isinstance(locale, (str, list)):
        raise ValueError("fingerprint.locale must be 'default', string, or list")

    languages = result["fingerprint"].get("languages")
    if not is_default(languages):
        if isinstance(languages, str):
            languages = [part.strip() for part in languages.split(",") if part.strip()]
        if not isinstance(languages, list) or not languages or not all(isinstance(v, str) and v.strip() for v in languages):
            raise ValueError("fingerprint.languages must be 'default', a locale string, or a non-empty list of locale strings")
        result["fingerprint"]["languages"] = [v.strip() for v in languages]

    tz = result["fingerprint"].get("timezone")
    if not is_default(tz) and (not isinstance(tz, str) or not tz.strip()):
        raise ValueError("fingerprint.timezone must be 'default' or a non-empty IANA timezone string")

    os_value = result["fingerprint"].get("os")
    if not is_default(os_value) and not isinstance(os_value, (str, list)):
        raise ValueError("fingerprint.os must be 'default', string, or list")

    screen = result["fingerprint"].get("screen")
    if not is_default(screen):
        if not isinstance(screen, dict):
            raise ValueError("fingerprint.screen must be 'default' or an object")
        allowed = {"min_width", "max_width", "min_height", "max_height"}
        unknown_screen = set(screen) - allowed
        if unknown_screen:
            raise ValueError(f"Unknown fingerprint.screen keys: {', '.join(sorted(unknown_screen))}")

    return result


def load_or_create_profile_config(path: Path, identity: str) -> dict[str, Any]:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return validate_profile_config(data, identity=identity)
    data = default_profile_config(identity)
    _atomic_write_json(path, data)
    return data


def patch_profile_config(path: Path, identity: str, patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("PATCH body must be a JSON object")
    current = load_or_create_profile_config(path, identity)
    allowed_top = {"fingerprint"}
    unknown_top = set(patch) - allowed_top
    if unknown_top:
        raise ValueError(f"Unknown profile config keys: {', '.join(sorted(unknown_top))}")
    fingerprint_changed = False
    if "fingerprint" in patch:
        if not isinstance(patch["fingerprint"], dict):
            raise ValueError("fingerprint patch must be an object")
        before = copy.deepcopy(current["fingerprint"])
        current["fingerprint"].update(copy.deepcopy(patch["fingerprint"]))
        fingerprint_changed = current["fingerprint"] != before
    if fingerprint_changed:
        current["baseline_stale"] = True
    current["updated_at"] = utc_now()
    current = validate_profile_config(current, identity=identity)
    _atomic_write_json(path, current)
    return current



def set_baseline_stale(path: Path, identity: str, stale: bool) -> dict[str, Any]:
    """Persist the fingerprint baseline stale flag for one Identity."""
    current = load_or_create_profile_config(path, identity)
    current["baseline_stale"] = bool(stale)
    current["updated_at"] = utc_now()
    current = validate_profile_config(current, identity=identity)
    _atomic_write_json(path, current)
    return current

def effective_fingerprint(run_cfg: dict[str, Any], profile_cfg: dict[str, Any]) -> dict[str, Any]:
    run_fp = run_cfg.get("fingerprint", {})
    profile_fp = profile_cfg.get("fingerprint", {})
    resolved: dict[str, Any] = {}
    for key in PROFILE_FINGERPRINT_KEYS:
        run_value = run_fp.get(key, DEFAULT)
        resolved[key] = copy.deepcopy(profile_fp.get(key, DEFAULT) if is_default(run_value) else run_value)
    return resolved


def generation_fingerprint(run_cfg: dict[str, Any], profile_cfg: dict[str, Any]) -> dict[str, Any]:
    effective = effective_fingerprint(run_cfg, profile_cfg)
    return {key: copy.deepcopy(effective.get(key, DEFAULT)) for key in GENERATION_KEYS}


def apply_direct_overrides(camou_config: dict[str, Any], effective: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(camou_config)
    timezone_value = effective.get("timezone", DEFAULT)
    if not is_default(timezone_value):
        result["timezone"] = str(timezone_value)
    languages_value = effective.get("languages", DEFAULT)
    if not is_default(languages_value):
        values = [languages_value] if isinstance(languages_value, str) else list(languages_value)
        result["locale:all"] = ", ".join(str(v) for v in values)
    dpr = effective.get("device_pixel_ratio", DEFAULT)
    if not is_default(dpr):
        result["window.devicePixelRatio"] = float(dpr)
    hc = effective.get("hardware_concurrency", DEFAULT)
    if not is_default(hc):
        result["navigator.hardwareConcurrency"] = int(hc)
    webgl = effective.get("webgl", DEFAULT)
    if not is_default(webgl):
        result["webGl:vendor"] = webgl["vendor"]
        result["webGl:renderer"] = webgl["renderer"]
    return result


def resolve_window(effective: dict[str, Any], camou_config: dict[str, Any]) -> dict[str, int] | None:
    value = effective.get("window", DEFAULT)
    if not is_default(value):
        return {"width": int(value["width"]), "height": int(value["height"])}
    # Persistent identity default: reuse the generated outer window dimensions.
    width = camou_config.get("window.outerWidth")
    height = camou_config.get("window.outerHeight")
    if width and height:
        return {"width": int(width), "height": int(height)}
    return None


def resolved_profile_snapshot(profile_cfg: dict[str, Any], effective: dict[str, Any], camou_config: dict[str, Any]) -> dict[str, Any]:
    window = resolve_window(effective, camou_config)
    return {
        "profile_config": copy.deepcopy(profile_cfg),
        "effective_request": copy.deepcopy(effective),
        "resolved": {
            "os": effective.get("os") if not is_default(effective.get("os")) else camou_config.get("navigator.platform"),
            "locale": effective.get("locale") if not is_default(effective.get("locale")) else (f"{camou_config.get('locale:language')}-{camou_config.get('locale:region')}" if camou_config.get("locale:language") and camou_config.get("locale:region") else camou_config.get("navigator.language")),
            "languages": effective.get("languages") if not is_default(effective.get("languages")) else camou_config.get("locale:all"),
            "timezone": effective.get("timezone") if not is_default(effective.get("timezone")) else camou_config.get("timezone"),
            "screen": {
                "width": camou_config.get("screen.width"),
                "height": camou_config.get("screen.height"),
                "avail_width": camou_config.get("screen.availWidth"),
                "avail_height": camou_config.get("screen.availHeight"),
            },
            "window": window,
            "inner": {
                "width": camou_config.get("window.innerWidth"),
                "height": camou_config.get("window.innerHeight"),
            },
            "device_pixel_ratio": camou_config.get("window.devicePixelRatio"),
            "hardware_concurrency": camou_config.get("navigator.hardwareConcurrency"),
            "webgl": {
                "vendor": camou_config.get("webGl:vendor"),
                "renderer": camou_config.get("webGl:renderer"),
            },
        },
    }
