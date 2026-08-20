from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


SUPPORTED_PROXY_SCHEMES = {"http", "https"}
DEPRECATED_PROXY_SCHEMES = {"socks5", "socks5h", "socks4"}


@dataclass
class ProxyError(RuntimeError):
    reason: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def proxy_geo_policy(cfg: dict[str, Any]) -> dict[str, bool]:
    """Return normalized proxy GEO policy.

    Backward compatible forms:
      "geoip": true|false

    Preferred v0.4.33 form:
      "geoip": {
        "enabled": true,
        "validate_identity": true,
        "fail_on_mismatch": false
      }

    `enabled` controls GEO use while generating/updating an Identity and whether
    GEO validation is attempted. It is intentionally NOT passed to normal browser
    launches: the persisted Identity config is the source of truth at runtime.
    """
    proxy = cfg.get("proxy", {})
    value = proxy.get("geoip", True)
    if isinstance(value, bool):
        return {
            "enabled": value,
            "validate_identity": value,
            "fail_on_mismatch": False,
        }
    if not isinstance(value, dict):
        raise ProxyError(
            "proxy_configuration_error",
            "proxy.geoip must be a boolean or an object.",
        )
    allowed = {"enabled", "validate_identity", "fail_on_mismatch"}
    unknown = set(value) - allowed
    if unknown:
        raise ProxyError(
            "proxy_configuration_error",
            f"Unknown proxy.geoip keys: {', '.join(sorted(unknown))}",
        )
    enabled = bool(value.get("enabled", True))
    return {
        "enabled": enabled,
        "validate_identity": enabled and bool(value.get("validate_identity", True)),
        "fail_on_mismatch": bool(value.get("fail_on_mismatch", False)),
    }


def validate_proxy_config(cfg: dict[str, Any]) -> dict[str, Any] | None:
    proxy = cfg.get("proxy", {})
    if not proxy.get("enabled", False):
        return None

    # Validate GEO policy early even though it does not affect proxy transport.
    proxy_geo_policy(cfg)

    server = str(proxy.get("server") or "").strip()
    if not server:
        raise ProxyError("proxy_configuration_error", "Proxy is enabled but proxy.server is empty.")

    parsed = urlsplit(server)
    scheme = parsed.scheme.lower()
    if scheme in DEPRECATED_PROXY_SCHEMES:
        raise ProxyError(
            "unsupported_proxy_type",
            f"Unsupported proxy type: {scheme}. SOCKS proxy support is deprecated; use HTTP or HTTPS.",
            {"proxy_scheme": scheme, "supported_proxy_types": ["http", "https"]},
        )
    if scheme not in SUPPORTED_PROXY_SCHEMES:
        raise ProxyError(
            "unsupported_proxy_type",
            f"Unsupported proxy type: {scheme or 'missing'}. Supported proxy types: http, https.",
            {"proxy_scheme": scheme or None, "supported_proxy_types": ["http", "https"]},
        )
    if not parsed.hostname:
        raise ProxyError("proxy_configuration_error", "proxy.server must contain a valid hostname.")

    return proxy


def classify_proxy_exception(exc: Exception) -> ProxyError | None:
    text = str(exc)
    low = text.lower()
    if "407" in low or "proxy authentication required" in low or "authentication" in low and "proxy" in low:
        return ProxyError("authentication_failed", "Proxy authentication failed.")
    if "certificate_verify_failed" in low or "certificate verify failed" in low or "hostname mismatch" in low:
        return ProxyError("tls_validation_failed", "Proxy TLS validation failed.")
    if "timed out" in low or "timeout" in low:
        return ProxyError("connection_timeout", "Proxy connection timed out.")
    if "proxyerror" in low or "unable to connect to proxy" in low or "proxy" in low and "connection" in low:
        return ProxyError("proxy_connection_failed", "Proxy connection failed.")
    return None
