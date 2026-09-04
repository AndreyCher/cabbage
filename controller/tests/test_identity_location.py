from app.identity_location import apply_location_defaults, location_defaults


def test_germany_location_defaults_are_browser_ready():
    assert location_defaults("de", "Europe/Berlin") == {
        "locale": "de-DE",
        "languages": ["de-DE", "de", "en-US", "en"],
        "timezone": "Europe/Berlin",
    }


def test_location_defaults_only_replace_default_values():
    config = {"fingerprint": {"locale": "fr-FR", "languages": "default", "timezone": "default", "os": "default"}}
    result = apply_location_defaults(config, "DE", "Europe/Berlin")
    assert result["fingerprint"]["locale"] == "fr-FR"
    assert result["fingerprint"]["languages"] == ["de-DE", "de", "en-US", "en"]
    assert result["fingerprint"]["timezone"] == "Europe/Berlin"
    assert result["fingerprint"]["os"] == "default"
    assert config["fingerprint"]["timezone"] == "default"
