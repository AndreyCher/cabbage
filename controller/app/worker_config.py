from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DEFAULT_DOMAIN_CONFIG: dict[str, Any] = {
    "identity_policy": {"allow_proxy_change": False},
    "browser": {
        "mode": "virtual", "humanize": 1.8, "enable_cache": True,
        "startup_attempts": 3, "startup_retry_delay_sec": 1.0,
        "version": "152.0.4-beta.28",
        "debug_display": {
            "size": "identity", "fallback": {"width": 1920, "height": 1080},
            "depth": 24, "window": "maximized", "position": {"x": 0, "y": 0},
            "novnc_scaling": "local",
        },
    },
    "recording": {"video": True, "backend": "x11", "video_size": "default", "debug_backend": "x11", "debug_fps": 15, "show_cursor": False},
    "debug": {"keep_alive": False, "message": "Automation finished. Browser remains open for manual control through noVNC."},
    "plugins": {"enabled": True, "items": {
        "playwright-recaptcha": {"enabled": False, "adapter": "app.plugins.playwright_recaptcha:PlaywrightRecaptchaPlugin", "config": {"default_wait": True, "image_challenge": False}},
        "hcaptcha-challenger": {"enabled": False, "adapter": "app.plugins.hcaptcha_challenger:HCaptchaChallengerPlugin", "config": {"click_checkbox": True, "disable_bezier_trajectory": True, "debug": False, "backend": "agentv"}},
        "consent-handler": {"enabled": True, "adapter": "app.plugins.consent_handler:ConsentHandlerPlugin", "config": {"policy": "accept_all", "timeout_ms": 10000, "required": False, "generic_fallback": True}},
    }},
    "fingerprint": {key: "default" for key in ("os", "preset", "screen", "locale", "window", "device_pixel_ratio", "hardware_concurrency", "webgl", "languages", "timezone")},
    "fingerprint_diagnostics": {"enabled": True, "save_snapshot": True, "compare_with_baseline": True, "update_baseline": False, "fail_on_change": False},
    "vm_diagnostics": {"enabled": False, "save_snapshot": True, "compare_with_baseline": True, "update_baseline": False, "keep_history": True, "label": "unknown"},
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentityPolicyConfig(StrictModel):
    allow_proxy_change: bool = False


class DisplayFallback(StrictModel):
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)


class DisplayPosition(StrictModel):
    x: int = 0
    y: int = 0


class DebugDisplayConfig(StrictModel):
    size: Literal["identity", "custom"] = "identity"
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fallback: DisplayFallback = Field(default_factory=DisplayFallback)
    depth: int = Field(default=24, ge=8, le=32)
    window: Literal["maximized", "normal"] = "maximized"
    position: DisplayPosition = Field(default_factory=DisplayPosition)
    novnc_scaling: Literal["local", "off"] = "local"

    @model_validator(mode="after")
    def custom_size_requires_dimensions(self) -> "DebugDisplayConfig":
        if self.size == "custom" and (self.width is None or self.height is None):
            raise ValueError("browser.debug_display width and height are required for custom size")
        return self


class BrowserConfig(StrictModel):
    mode: Literal["virtual", "headless", "debug"] = "virtual"
    humanize: float = Field(default=1.8, ge=0)
    enable_cache: bool = True
    startup_attempts: int = Field(default=3, ge=1, le=20)
    startup_retry_delay_sec: float = Field(default=1.0, ge=0, le=300)
    version: str = Field(default="152.0.4-beta.28", min_length=1, max_length=128)
    debug_display: DebugDisplayConfig = Field(default_factory=DebugDisplayConfig)


class VideoSize(StrictModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class RecordingConfig(StrictModel):
    video: bool = True
    backend: Literal["x11", "playwright"] = "x11"
    video_size: Literal["default", "playwright-default"] | VideoSize = "default"
    debug_backend: Literal["x11", "playwright"] = "x11"
    debug_fps: int = Field(default=15, ge=1, le=120)
    show_cursor: bool = False


class FingerprintConfig(StrictModel):
    os: Any = "default"
    preset: Any = "default"
    screen: Any = "default"
    locale: Any = "default"
    window: Any = "default"
    device_pixel_ratio: Any = "default"
    hardware_concurrency: Any = "default"
    webgl: Any = "default"
    languages: Any = "default"
    timezone: Any = "default"

    @field_validator("window")
    @classmethod
    def validate_window(cls, value: Any) -> Any:
        if value == "default":
            return value
        if not isinstance(value, dict) or set(value) != {"width", "height"}:
            raise ValueError("fingerprint.window must be 'default' or {width,height}")
        if int(value["width"]) <= 0 or int(value["height"]) <= 0:
            raise ValueError("fingerprint.window dimensions must be positive")
        return {"width": int(value["width"]), "height": int(value["height"])}


class FingerprintDiagnosticsConfig(StrictModel):
    enabled: bool = True
    save_snapshot: bool = True
    compare_with_baseline: bool = True
    update_baseline: bool = False
    fail_on_change: bool = False


class VMDiagnosticsConfig(StrictModel):
    enabled: bool = False
    save_snapshot: bool = True
    compare_with_baseline: bool = True
    update_baseline: bool = False
    keep_history: bool = True
    label: str = Field(default="unknown", max_length=255)


class DebugConfig(StrictModel):
    keep_alive: bool = False
    message: str | None = Field(default=None, max_length=4096)


class PluginItemConfig(StrictModel):
    enabled: bool = False
    adapter: str = Field(min_length=1, max_length=512)
    config: dict[str, Any] = Field(default_factory=dict)


class PluginsConfig(StrictModel):
    enabled: bool = True
    items: dict[str, PluginItemConfig] = Field(default_factory=dict)


class WorkerConfig(StrictModel):
    """All user-configurable worker domain options; infrastructure keys are excluded."""

    identity_policy: IdentityPolicyConfig | None = None
    browser: BrowserConfig | None = None
    recording: RecordingConfig | None = None
    fingerprint: FingerprintConfig | None = None
    fingerprint_diagnostics: FingerprintDiagnosticsConfig | None = None
    vm_diagnostics: VMDiagnosticsConfig | None = None
    debug: DebugConfig | None = None
    plugins: PluginsConfig | None = None

    def overrides(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ProxyGeoConfig(StrictModel):
    enabled: bool = True
    validate_identity: bool = True
    fail_on_mismatch: bool = False
