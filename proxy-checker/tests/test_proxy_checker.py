import pytest

from app.main import deep_merge, normalize


def test_database_settings_deep_merge_over_local_defaults():
    assert deep_merge({"timeout": 20, "provider": {"enabled": True, "url": "x"}}, {"timeout": 5, "provider": {"enabled": False}}) == {"timeout": 5, "provider": {"enabled": False, "url": "x"}}


@pytest.mark.parametrize("provider,payload", [
    ("ipwhois", {"ip": "1.2.3.4", "country_code": "de", "country": "Germany", "timezone": {"id": "Europe/Berlin"}}),
    ("freeipapi", {"ipAddress": "1.2.3.4", "countryCode": "DE", "countryName": "Germany", "timeZone": "Europe/Berlin"}),
    ("ipapi_co", {"ip": "1.2.3.4", "country_code": "DE", "country_name": "Germany", "timezone": "Europe/Berlin"}),
])
def test_free_provider_responses_normalize(provider, payload):
    result = normalize(provider, payload)
    assert result == {"exit_ip": "1.2.3.4", "country_code": "DE", "country_name": "Germany", "timezone": "Europe/Berlin"}


def test_invalid_provider_response_is_rejected():
    with pytest.raises(ValueError):
        normalize("ipwhois", {"success": False, "message": "quota"})


def test_location_without_timezone_is_rejected():
    with pytest.raises(ValueError, match="timezone"):
        normalize("ipwhois", {"ip": "1.2.3.4", "country_code": "DE", "country": "Germany"})
