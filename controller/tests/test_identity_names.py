from app.identity_names import country_from_config, numbered_identity_names, random_identity_name


def test_numbered_identity_names_append_sequence():
    assert numbered_identity_names("account", 3) == ["account-1", "account-2", "account-3"]


def test_country_is_inferred_from_explicit_fingerprint_locale():
    assert country_from_config({"fingerprint": {"locale": "fr-FR"}}) == "FR"
    assert country_from_config({"fingerprint": {"locale": "default"}}) is None


def test_random_identity_name_is_country_styled_and_unique():
    existing: set[str] = set()
    names = {random_identity_name("DE", existing) for _ in range(20)}
    assert len(names) == 20
    assert all(name == name.lower() and name.count("-") == 2 for name in names)
    assert names == existing
