from app.diagnostics import compare_proxy_geo_to_identity
from app.profile_config import apply_direct_overrides, default_profile_config, validate_profile_config
from app.proxy import proxy_geo_policy


def test_geo_policy_bool_backward_compatibility():
    cfg = {"proxy": {"enabled": True, "geoip": True}}
    assert proxy_geo_policy(cfg) == {
        "enabled": True,
        "validate_identity": True,
        "fail_on_mismatch": False,
    }


def test_geo_policy_object():
    cfg = {"proxy": {"enabled": True, "geoip": {
        "enabled": True,
        "validate_identity": True,
        "fail_on_mismatch": True,
    }}}
    assert proxy_geo_policy(cfg)["fail_on_mismatch"] is True


def test_proxy_geo_mismatch_detected():
    proxy_geo = {"enabled": True, "country_code": "DE", "timezone": "Europe/Berlin"}
    identity = {"region": "US", "locale": "en-US", "timezone": "America/New_York"}
    result = compare_proxy_geo_to_identity(proxy_geo, identity)
    assert result["checked"] is True
    assert result["mismatch"] is True
    assert {m["field"] for m in result["mismatches"]} == {"country/locale_region", "timezone"}


def test_proxy_geo_match():
    proxy_geo = {"enabled": True, "country_code": "DE", "timezone": "Europe/Berlin"}
    identity = {"region": "DE", "locale": "de-DE", "timezone": "Europe/Berlin"}
    result = compare_proxy_geo_to_identity(proxy_geo, identity)
    assert result["checked"] is True
    assert result["mismatch"] is False


def test_profile_supports_timezone_and_languages():
    profile = default_profile_config("test")
    profile["fingerprint"]["timezone"] = "Europe/Berlin"
    profile["fingerprint"]["languages"] = ["de-DE", "de"]
    validated = validate_profile_config(profile, identity="test")
    assert validated["fingerprint"]["timezone"] == "Europe/Berlin"
    assert validated["fingerprint"]["languages"] == ["de-DE", "de"]

    camou = {"timezone": "UTC", "locale:all": "en-US, en"}
    effective = {"timezone": "Europe/Berlin", "languages": ["de-DE", "de"]}
    updated = apply_direct_overrides(camou, effective)
    assert updated["timezone"] == "Europe/Berlin"
    assert updated["locale:all"] == "de-DE, de"
