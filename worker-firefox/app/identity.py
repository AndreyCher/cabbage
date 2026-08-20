from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from browserforge.fingerprints import Screen
from camoufox.utils import launch_options

from .proxy import ProxyError, proxy_geo_policy, validate_proxy_config

APP_VERSION = "0.5.22"
IDENTITY_SCHEMA_VERSION = 4
DEFAULT = "default"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _is_default(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.lower() == DEFAULT)


def _screen_from_config(value: Any) -> Screen | None:
    if _is_default(value):
        return None
    if not isinstance(value, dict):
        raise ValueError("fingerprint.screen must be 'default' or an object")
    allowed = {"min_width", "max_width", "min_height", "max_height"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown fingerprint.screen keys: {', '.join(sorted(unknown))}")
    return Screen(
        min_width=value.get("min_width"),
        max_width=value.get("max_width"),
        min_height=value.get("min_height"),
        max_height=value.get("max_height"),
    )


def _playwright_proxy(cfg: dict[str, Any]) -> dict[str, str] | None:
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


def _proxy_identity(cfg: dict[str, Any]) -> dict[str, Any]:
    proxy = cfg.get("proxy", {})
    if not proxy.get("enabled", False):
        return {"enabled": False, "proxy_id": None}

    server = proxy.get("server") or ""
    username = proxy.get("username") or ""
    explicit_id = proxy.get("proxy_id")
    derived = hashlib.sha256(f"{server}|{username}".encode()).hexdigest()[:16]
    return {
        "enabled": True,
        "proxy_id": explicit_id or derived,
        "server": server,
        "username": username,
        "geoip": proxy_geo_policy(cfg),
    }


def identity_paths(identity_name: str, identities_root: str | Path) -> dict[str, Path]:
    root = Path(identities_root) / identity_name
    return {
        "root": root,
        "profile": root / "profile",
        "metadata": root / "identity.json",
        "config": root / "config.json",
        # v0.2 compatibility only. v0.3 stores the config inside identity.json.
        "legacy_camoufox_config": root / "camoufox-config.json",
    }


def reset_identity(identity_name: str, identities_root: str | Path) -> None:
    root = identity_paths(identity_name, identities_root)["root"]
    if root.exists():
        shutil.rmtree(root)


def _fingerprint_request(cfg: dict[str, Any]) -> dict[str, Any]:
    fp = cfg.get("fingerprint", {})
    return {
        "os": fp.get("os", DEFAULT),
        "preset": fp.get("preset", DEFAULT),
        "screen": fp.get("screen", DEFAULT),
        "locale": fp.get("locale", DEFAULT),
        "languages": fp.get("languages", DEFAULT),
        "timezone": fp.get("timezone", DEFAULT),
    }


def _extract_camou_config(options: dict[str, Any]) -> dict[str, Any]:
    env = options.get("env") or {}
    chunks: list[tuple[int, str]] = []
    for key, value in env.items():
        if key.startswith("CAMOU_CONFIG_"):
            chunks.append((int(key.rsplit("_", 1)[1]), str(value)))
    if not chunks:
        raise RuntimeError("Camoufox launch_options did not produce CAMOU_CONFIG")
    blob = "".join(value for _, value in sorted(chunks))
    return json.loads(blob)


def _generation_kwargs(cfg: dict[str, Any]) -> dict[str, Any]:
    """Build only explicit Camoufox generation overrides.

    Any JSON value equal to "default" is intentionally omitted so Camoufox owns
    the default generation logic.
    """
    fp = cfg.get("fingerprint", {})
    browser = cfg.get("browser", {})

    config_overrides: dict[str, Any] = {}
    timezone_value = fp.get("timezone", DEFAULT)
    if not _is_default(timezone_value):
        if not isinstance(timezone_value, str) or not timezone_value.strip():
            raise ValueError("fingerprint.timezone must be 'default' or a non-empty IANA timezone string")
        # Camoufox has no standalone high-level timezone argument.  This is an
        # intentional persistent-Identity override, so keep it in config and
        # explicitly acknowledge the low-level override below.
        config_overrides["timezone"] = timezone_value.strip()

    kwargs: dict[str, Any] = {
        "config": config_overrides,
        "humanize": browser.get("humanize", 1.8),
        "enable_cache": browser.get("enable_cache", True),
        "proxy": _playwright_proxy(cfg),
        "geoip": proxy_geo_policy(cfg)["enabled"] if cfg.get("proxy", {}).get("enabled") else None,
        "browser": browser.get("version", "152.0.4-beta.28"),
        "headless": False,
        # v0.5.1: persistent timezone/location config is intentional.  Locale
        # itself is passed through Camoufox's public `locale=` API below.
        "i_know_what_im_doing": True,
    }

    os_value = fp.get("os", DEFAULT)
    if not _is_default(os_value):
        kwargs["os"] = os_value

    preset_value = fp.get("preset", DEFAULT)
    if not _is_default(preset_value):
        if not isinstance(preset_value, bool):
            raise ValueError("fingerprint.preset must be 'default', true or false")
        kwargs["fingerprint_preset"] = preset_value

    screen_value = fp.get("screen", DEFAULT)
    screen = _screen_from_config(screen_value)
    if screen is not None:
        kwargs["screen"] = screen

    locale_value = fp.get("locale", DEFAULT)
    languages_value = fp.get("languages", DEFAULT)

    accepted_locales: list[str] = []
    if not _is_default(locale_value):
        raw_locales = [locale_value] if isinstance(locale_value, str) else locale_value
        if not isinstance(raw_locales, list) or not raw_locales:
            raise ValueError("fingerprint.locale must be 'default', a locale string, or a non-empty list")
        accepted_locales.extend(str(value).strip() for value in raw_locales if str(value).strip())

    if not _is_default(languages_value):
        if isinstance(languages_value, str):
            languages_value = [part.strip() for part in languages_value.split(",") if part.strip()]
        if not isinstance(languages_value, list) or not languages_value:
            raise ValueError("fingerprint.languages must be 'default', a locale string, or a non-empty list")
        for value in languages_value:
            value = str(value).strip()
            if value and value not in accepted_locales:
                accepted_locales.append(value)

    # Use Camoufox's supported locale API instead of writing locale:* keys into
    # the low-level config.  The first locale is authoritative for Intl while
    # the remaining values become accepted browser languages.
    if accepted_locales:
        kwargs["locale"] = accepted_locales if len(accepted_locales) > 1 else accepted_locales[0]

    return {key: value for key, value in kwargs.items() if value is not None}


def _generate_camoufox_config(cfg: dict[str, Any]) -> dict[str, Any]:
    options = launch_options(**_generation_kwargs(cfg))
    return _extract_camou_config(options)


def _persistent_fields(camou_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "canvas_seed": camou_config.get("canvas:seed"),
        "audio_seed": camou_config.get("audio:seed"),
        "font_spacing_seed": camou_config.get("fonts:spacing_seed"),
        "history_length": camou_config.get("window.history.length"),
    }




def _location_identity(camou_config: dict[str, Any]) -> dict[str, Any]:
    """Extract the persistent locale/location-facing Identity fields."""
    language = camou_config.get("locale:language")
    region = camou_config.get("locale:region")
    script = camou_config.get("locale:script")
    all_locales = camou_config.get("locale:all")
    locale = None
    if language and region:
        locale = f"{language}-{region}"
    elif language:
        locale = str(language)
    languages: list[str] = []
    if isinstance(all_locales, str):
        languages = [part.strip() for part in all_locales.split(",") if part.strip()]
    elif isinstance(all_locales, list):
        languages = [str(part).strip() for part in all_locales if str(part).strip()]
    if not languages and locale:
        languages = [locale]
    return {
        "locale": locale,
        "language": language,
        "region": region,
        "script": script,
        "languages": languages,
        "timezone": camou_config.get("timezone"),
        "latitude": camou_config.get("geolocation:latitude"),
        "longitude": camou_config.get("geolocation:longitude"),
    }

def _new_metadata(cfg: dict[str, Any], camou_config: dict[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "identity": cfg["identity"],
        "created_at": created_at or now,
        "updated_at": now,
        "last_used_at": now,
        "created_by_app_version": APP_VERSION,
        "last_app_version": APP_VERSION,
        "profile_dir": "profile",
        "fingerprint_request": _fingerprint_request(cfg),
        "proxy_identity": _proxy_identity(cfg),
        "persistent_fields": _persistent_fields(camou_config),
        "location_identity": _location_identity(camou_config),
        # Canonical persistent device fingerprint/config for this Identity.
        "camoufox_config": camou_config,
    }


def _migrate_v2(paths: dict[str, Path], metadata: dict[str, Any], logger=None) -> dict[str, Any]:
    if metadata.get("schema_version") != 2:
        return metadata
    legacy = paths["legacy_camoufox_config"]
    if not legacy.exists():
        raise RuntimeError("Cannot migrate v0.2 Identity: camoufox-config.json is missing")
    camou_config = json.loads(legacy.read_text(encoding="utf-8"))
    migrated = dict(metadata)
    migrated["schema_version"] = IDENTITY_SCHEMA_VERSION
    migrated["updated_at"] = _utc_now()
    migrated["last_app_version"] = APP_VERSION
    migrated["fingerprint_request"] = metadata.get("identity_constraints", {})
    migrated.pop("identity_constraints", None)
    migrated.pop("config_storage", None)
    migrated["camoufox_config"] = camou_config
    migrated["persistent_fields"] = _persistent_fields(camou_config)
    migrated["location_identity"] = _location_identity(camou_config)
    _write_json(paths["metadata"], migrated)
    if logger:
        logger.info("Migrated Identity %s from schema 2 to schema 4", migrated.get("identity"))
    return migrated


def _validate_proxy(cfg: dict[str, Any], metadata: dict[str, Any]) -> None:
    expected_proxy = _proxy_identity(cfg)
    saved_proxy = metadata.get("proxy_identity", {})
    allow_proxy_change = bool(cfg.get("identity_policy", {}).get("allow_proxy_change", False))
    if saved_proxy.get("proxy_id") != expected_proxy.get("proxy_id") and not allow_proxy_change:
        raise ProxyError(
            "proxy_change_not_allowed",
            f"Proxy identity change blocked for Identity {cfg['identity']!r}: "
            f"{saved_proxy.get('proxy_id')!r} -> {expected_proxy.get('proxy_id')!r}. "
            "Set identity_policy.allow_proxy_change=true for one intentional run.",
            {
                "identity": cfg["identity"],
                "current_proxy_id": saved_proxy.get("proxy_id"),
                "requested_proxy_id": expected_proxy.get("proxy_id"),
            },
        )




def _migrate_v3(metadata: dict[str, Any], paths: dict[str, Path], logger=None) -> dict[str, Any]:
    if metadata.get("schema_version") != 3:
        return metadata
    camou_config = metadata.get("camoufox_config")
    if not isinstance(camou_config, dict) or not camou_config:
        raise RuntimeError("Cannot migrate schema 3 Identity: camoufox_config is missing")
    migrated = dict(metadata)
    migrated["schema_version"] = IDENTITY_SCHEMA_VERSION
    migrated["updated_at"] = _utc_now()
    migrated["last_app_version"] = APP_VERSION
    migrated["location_identity"] = _location_identity(camou_config)
    _write_json(paths["metadata"], migrated)
    if logger:
        logger.info("Migrated Identity %s from schema 3 to schema 4", migrated.get("identity"))
    return migrated

def load_or_create_identity(cfg: dict[str, Any], logger=None, *, update: bool = False, identities_root: str | Path) -> dict[str, Any]:
    name = cfg["identity"]
    paths = identity_paths(name, identities_root)
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["profile"].mkdir(parents=True, exist_ok=True)

    if paths["metadata"].exists():
        metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
        metadata = _migrate_v2(paths, metadata, logger=logger)
        metadata = _migrate_v3(metadata, paths, logger=logger)
        if metadata.get("schema_version") != IDENTITY_SCHEMA_VERSION:
            raise RuntimeError(
                f"Identity {name!r} uses schema {metadata.get('schema_version')}; "
                f"expected {IDENTITY_SCHEMA_VERSION}. Reset or migrate the identity."
            )

        _validate_proxy(cfg, metadata)

        requested_fp = _fingerprint_request(cfg)
        saved_fp = metadata.get("fingerprint_request", {})
        profile_changed = requested_fp != saved_fp

        if update or profile_changed:
            old_fields = metadata.get("persistent_fields", {})
            camou_config = _generate_camoufox_config(cfg)
            created_at = metadata.get("created_at")
            metadata = _new_metadata(cfg, camou_config, created_at=created_at)
            metadata["previous_persistent_fields"] = old_fields
            _write_json(paths["metadata"], metadata)
            if logger:
                if profile_changed and not update:
                    logger.warning("Identity profile generation parameters changed; regenerated fingerprint/device config for %s while preserving browser profile", name)
                else:
                    logger.warning("Updated fingerprint/device config for existing Identity %s; profile was preserved", name)
                logger.info(
                    "New persistent seeds: canvas=%s audio=%s fonts=%s",
                    metadata["persistent_fields"]["canvas_seed"],
                    metadata["persistent_fields"]["audio_seed"],
                    metadata["persistent_fields"]["font_spacing_seed"],
                )
            return {"camou_config": camou_config, "metadata": metadata, "paths": paths, "created": False, "updated": True}

        camou_config = metadata.get("camoufox_config")
        if not isinstance(camou_config, dict) or not camou_config:
            raise RuntimeError(f"Identity {name!r} has no persisted camoufox_config")

        metadata["last_used_at"] = _utc_now()
        metadata["last_app_version"] = APP_VERSION
        _write_json(paths["metadata"], metadata)
        if logger:
            logger.info("Loaded stable identity %s (created %s)", name, metadata.get("created_at"))
        return {"camou_config": camou_config, "metadata": metadata, "paths": paths, "created": False, "updated": False}

    if update:
        raise RuntimeError(f"Cannot update Identity {name!r}: it does not exist yet")

    camou_config = _generate_camoufox_config(cfg)
    metadata = _new_metadata(cfg, camou_config)
    _write_json(paths["metadata"], metadata)
    if logger:
        logger.info("Created new stable identity %s", name)
        logger.info(
            "Persistent seeds: canvas=%s audio=%s fonts=%s",
            metadata["persistent_fields"]["canvas_seed"],
            metadata["persistent_fields"]["audio_seed"],
            metadata["persistent_fields"]["font_spacing_seed"],
        )
    return {"camou_config": camou_config, "metadata": metadata, "paths": paths, "created": True, "updated": False}
