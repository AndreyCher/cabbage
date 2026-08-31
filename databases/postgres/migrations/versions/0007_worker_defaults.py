"""Seed Controller-owned worker domain defaults.

Revision ID: 0007_worker_defaults
Revises: 0006_full_worker_control
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_worker_defaults"
down_revision = "0006_full_worker_control"
branch_labels = None
depends_on = None


DEFAULTS = {
    "identity_policy": {"allow_proxy_change": False},
    "browser": {"mode": "virtual", "humanize": 1.8, "enable_cache": True, "startup_attempts": 3, "startup_retry_delay_sec": 1.0, "version": "152.0.4-beta.28", "debug_display": {"size": "identity", "fallback": {"width": 1920, "height": 1080}, "depth": 24, "window": "maximized", "position": {"x": 0, "y": 0}, "novnc_scaling": "local"}},
    "recording": {"video": True, "backend": "x11", "video_size": "default", "debug_backend": "x11", "debug_fps": 15, "show_cursor": False},
    "fingerprint": {"os": "default", "preset": "default", "screen": "default", "locale": "default", "window": "default", "device_pixel_ratio": "default", "hardware_concurrency": "default", "webgl": "default", "languages": "default", "timezone": "default"},
    "fingerprint_diagnostics": {"enabled": True, "save_snapshot": True, "compare_with_baseline": True, "update_baseline": False, "fail_on_change": False},
    "vm_diagnostics": {"enabled": False, "save_snapshot": True, "compare_with_baseline": True, "update_baseline": False, "keep_history": True, "label": "unknown"},
    "debug": {"keep_alive": False, "message": "Automation finished. Browser remains open for manual control through noVNC."},
    "plugins": {"enabled": True, "items": {
        "playwright-recaptcha": {"enabled": False, "adapter": "app.plugins.playwright_recaptcha:PlaywrightRecaptchaPlugin", "config": {"default_wait": True, "image_challenge": False}},
        "hcaptcha-challenger": {"enabled": False, "adapter": "app.plugins.hcaptcha_challenger:HCaptchaChallengerPlugin", "config": {"click_checkbox": True, "disable_bezier_trajectory": True, "debug": False, "backend": "agentv"}},
        "consent-handler": {"enabled": True, "adapter": "app.plugins.consent_handler:ConsentHandlerPlugin", "config": {"policy": "accept_all", "timeout_ms": 10000, "required": False, "generic_fallback": True}},
    }},
}


def upgrade():
    settings = sa.table(
        "controller_settings",
        sa.column("key", sa.String()),
        sa.column("value", postgresql.JSONB()),
        sa.column("revision", sa.Integer()),
    )
    op.bulk_insert(settings, [{"key": "worker_defaults", "value": DEFAULTS, "revision": 1}])


def downgrade():
    op.execute(sa.text("DELETE FROM controller_settings WHERE key = 'worker_defaults'"))
