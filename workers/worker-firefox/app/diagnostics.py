from __future__ import annotations

from typing import Any

import requests
import urllib3

from .proxy import validate_proxy_config


def _requests_proxy(cfg: dict[str, Any]) -> dict[str, str] | None:
    proxy = validate_proxy_config(cfg)
    if proxy is None:
        return None

    server = proxy.get("server")

    if proxy.get("username"):
        scheme, rest = server.split("://", 1)
        auth = f"{proxy['username']}:{proxy.get('password', '')}@"
        url = f"{scheme}://{auth}{rest}"
    else:
        url = server
    return {"http": url, "https": url}


def public_ip(proxies: dict[str, str] | None = None, *, verify_ssl: bool = True) -> str | None:
    try:
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=20, verify=verify_ssl)
        r.raise_for_status()
        return r.json().get("ip")
    except Exception as exc:  # diagnostics must not abort the test
        return f"ERROR: {exc}"


def network_preflight(cfg: dict[str, Any]) -> dict[str, Any]:
    proxy = validate_proxy_config(cfg)
    verify_ssl = bool((proxy or {}).get("verify_ssl", True))
    return {
        "container_direct_ip": public_ip(),
        "proxy_public_ip": public_ip(_requests_proxy(cfg), verify_ssl=verify_ssl) if proxy else None,
        "proxy_verify_ssl": verify_ssl if proxy else None,
    }


def browser_identity(page) -> dict[str, Any]:
    js = r"""
    async () => {
      let webgl = {};
      try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');
        webgl = {
          vendor: gl ? gl.getParameter(gl.VENDOR) : null,
          renderer: gl ? gl.getParameter(gl.RENDERER) : null,
          unmaskedVendor: (gl && dbg) ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null,
          unmaskedRenderer: (gl && dbg) ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null
        };
      } catch (e) { webgl = {error: String(e)}; }

      let publicIp = null;
      try {
        const r = await fetch('https://api.ipify.org?format=json');
        publicIp = (await r.json()).ip;
      } catch (e) { publicIp = 'ERROR: ' + String(e); }

      return {
        publicIp,
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        languages: navigator.languages,
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory ?? null,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        screen: {
          width: screen.width,
          height: screen.height,
          availWidth: screen.availWidth,
          availHeight: screen.availHeight,
          colorDepth: screen.colorDepth,
          pixelDepth: screen.pixelDepth
        },
        viewport: {width: innerWidth, height: innerHeight, devicePixelRatio},
        webgl
      };
    }
    """
    return page.evaluate(js)


def proxy_geo_snapshot(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve the proxy exit GEO without changing browser fingerprint settings.

    This is diagnostics/validation only. Failure to resolve GEO is returned as an
    error object so normal runs are not coupled to the third-party lookup.
    """
    proxy = validate_proxy_config(cfg)
    if proxy is None:
        return None
    from .proxy import proxy_geo_policy
    policy = proxy_geo_policy(cfg)
    if not policy["enabled"] or not policy["validate_identity"]:
        return {"enabled": False, "reason": "validation_disabled"}

    verify_ssl = bool(proxy.get("verify_ssl", True))
    try:
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.get(
            "https://ipwho.is/",
            proxies=_requests_proxy(cfg),
            timeout=20,
            verify=verify_ssl,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("success") is False:
            return {"enabled": True, "error": data.get("message") or "GeoIP lookup failed"}
        tz = data.get("timezone") or {}
        return {
            "enabled": True,
            "ip": data.get("ip"),
            "country": data.get("country"),
            "country_code": data.get("country_code"),
            "region": data.get("region"),
            "city": data.get("city"),
            "timezone": tz.get("id") if isinstance(tz, dict) else tz,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
    except Exception as exc:
        return {"enabled": True, "error": str(exc)}


def compare_proxy_geo_to_identity(
    proxy_geo: dict[str, Any] | None,
    identity_location: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare proxy exit geography to persistent Identity locale/timezone."""
    result: dict[str, Any] = {
        "checked": False,
        "mismatch": False,
        "mismatches": [],
        "proxy": proxy_geo,
        "identity": identity_location or {},
    }
    if not proxy_geo or not proxy_geo.get("enabled") or proxy_geo.get("error"):
        result["reason"] = "proxy_geo_unavailable" if proxy_geo and proxy_geo.get("error") else "disabled"
        return result

    identity_location = identity_location or {}
    mismatches: list[dict[str, Any]] = []
    proxy_country = str(proxy_geo.get("country_code") or "").upper() or None
    identity_region = str(identity_location.get("region") or "").upper() or None
    if proxy_country and identity_region and proxy_country != identity_region:
        mismatches.append({
            "field": "country/locale_region",
            "identity": identity_region,
            "proxy": proxy_country,
        })

    proxy_timezone = proxy_geo.get("timezone")
    identity_timezone = identity_location.get("timezone")
    if proxy_timezone and identity_timezone and proxy_timezone != identity_timezone:
        mismatches.append({
            "field": "timezone",
            "identity": identity_timezone,
            "proxy": proxy_timezone,
        })

    result["checked"] = True
    result["mismatches"] = mismatches
    result["mismatch"] = bool(mismatches)
    return result
